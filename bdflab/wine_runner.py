"""Exécution isolée sous Wine : préfixes jetables, limites, mesures, journaux.

Règles de ressources (mission §7) :
  * un préfixe gabarit est créé une fois par version de Wine, puis copié pour chaque exécution
    (les binaires de ``drive_c/windows/system32`` et ``syswow64`` sont liés en dur : Wine ne les
    modifie jamais en place, le registre est réécrit par renommage) ;
  * un verrou limite le nombre d'exécutions Wine simultanées (défaut : 1) ;
  * chaque exécution a un délai maximal ; au-delà, le groupe de processus est tué puis
    ``wineserver -k`` est envoyé au préfixe ;
  * les préfixes sont détruits après chaque exécution, seuls journaux et traces sont conservés ;
  * contrôle préalable : espace disque, mémoire, erreurs SMART si ``smartctl`` est disponible.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

DEFAULT_DEBUG = "+relay,+tid,+timestamp,+seh,warn+module,+loaddll"
# canaux relay exclus pour alléger la trace (allocations mémoire, sections critiques, chaînes)
DEFAULT_RELAY_EXCLUDE = (
    "ntdll.RtlEnterCriticalSection;ntdll.RtlLeaveCriticalSection;ntdll.RtlAllocateHeap;ntdll.RtlFreeHeap;"
    "ntdll.RtlReAllocateHeap;ntdll.RtlSizeHeap;ntdll.memcpy;ntdll.memset;ntdll.memmove;ntdll.wcslen;"
    "ntdll.strlen;ntdll.RtlTryEnterCriticalSection;ntdll.RtlInitializeCriticalSectionEx;"
    "ntdll.RtlDeleteCriticalSection;ntdll.NtQueryPerformanceCounter;ntdll.RtlGetCurrentPeb;"
    "ntdll.NtQueryVirtualMemory;ntdll.NtProtectVirtualMemory;ntdll.RtlPcToFileHeader;"
    "KERNEL32.GetLastError;KERNEL32.SetLastError;KERNELBASE.GetLastError;KERNELBASE.SetLastError;"
    "KERNEL32.TlsGetValue;KERNELBASE.TlsGetValue;msvcrt.*"
)


def find_wine(bin_dir: str | None = None) -> Path:
    cands = []
    if bin_dir:
        cands.append(Path(bin_dir))
    env_dir = os.environ.get("BDFLAB_WINE_BIN")
    if env_dir:
        cands.append(Path(env_dir))
    cands += [Path("/opt/wine-stable/bin"), Path("/opt/wine-devel/bin"), Path("/usr/local/bin"), Path("/usr/bin")]
    for c in cands:
        if (c / "wine").exists():
            return c
    raise FileNotFoundError("wine introuvable (BDFLAB_WINE_BIN ou /opt/wine-stable/bin)")


@dataclass
class WineInfo:
    bin_dir: str
    version: str
    package: str
    lib_dir: str

    def to_dict(self) -> dict:
        return asdict(self)


def wine_info(bin_dir: str | None = None) -> WineInfo:
    b = find_wine(bin_dir)
    env = dict(os.environ, WINEDEBUG="-all")
    version = subprocess.run([str(b / "wine"), "--version"], capture_output=True, text=True, env=env, timeout=60).stdout.strip()
    pkg = ""
    try:
        q = subprocess.run(["dpkg-query", "-W", "-f=${Package} ${Version}", "wine-stable"], capture_output=True, text=True, timeout=30)
        if q.returncode == 0:
            pkg = q.stdout.strip()
    except Exception:
        pass
    lib_dir = str((b / ".." / "lib" / "wine").resolve())
    return WineInfo(bin_dir=str(b), version=version, package=pkg, lib_dir=lib_dir)


@dataclass
class Preflight:
    ok: bool
    disk_free_gb: float
    mem_available_gb: float
    smart: str
    wine_processes: int
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def preflight(work_dir: Path, min_disk_gb: float = 4.0, min_mem_gb: float = 1.0, max_wine_procs: int = 2) -> Preflight:
    work_dir.mkdir(parents=True, exist_ok=True)
    du = shutil.disk_usage(work_dir)
    disk_free = du.free / 1e9
    msgs: list[str] = []
    mem_avail = 0.0
    if psutil:
        mem_avail = psutil.virtual_memory().available / 1e9
    smart = "non vérifié"
    if shutil.which("smartctl"):
        try:
            dev = subprocess.run(["findmnt", "-n", "-o", "SOURCE", "--target", str(work_dir)], capture_output=True, text=True, timeout=10).stdout.strip()
            r = subprocess.run(["smartctl", "-H", dev], capture_output=True, text=True, timeout=30)
            smart = "OK" if "PASSED" in r.stdout else f"indéterminé ({r.returncode})"
            if "FAILED" in r.stdout:
                smart = "ECHEC"
                msgs.append(f"SMART en échec sur {dev} : aucun test autorisé")
        except Exception as exc:
            smart = f"indisponible ({exc.__class__.__name__})"
    else:
        smart = "smartctl absent (disque virtuel ou non installé) : non vérifiable"
    n_wine = 0
    if psutil:
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"] in {"wine", "wine64", "wineserver", "wine-preloader", "wine64-preloader"}:
                    n_wine += 1
            except Exception:
                pass
    ok = disk_free >= min_disk_gb and (not psutil or mem_avail >= min_mem_gb) and smart != "ECHEC"
    if disk_free < min_disk_gb:
        msgs.append(f"espace disque insuffisant : {disk_free:.1f} Go < {min_disk_gb} Go")
    if psutil and mem_avail < min_mem_gb:
        msgs.append(f"mémoire disponible insuffisante : {mem_avail:.1f} Go")
    return Preflight(ok=ok, disk_free_gb=round(disk_free, 2), mem_available_gb=round(mem_avail, 2), smart=smart,
                     wine_processes=n_wine, messages=msgs)


class RunLock:
    """Verrou inter-processus limitant les exécutions Wine simultanées (1 par défaut)."""

    def __init__(self, work_dir: Path, slots: int = 1):
        self.work_dir = work_dir
        self.slots = max(1, slots)
        self._fh = None

    def __enter__(self):
        self.work_dir.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + 3600
        while time.time() < deadline:
            for i in range(self.slots):
                fh = open(self.work_dir / f".run-slot-{i}.lock", "w")
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._fh = fh
                    return self
                except OSError:
                    fh.close()
            time.sleep(0.5)
        raise TimeoutError("aucun créneau d'exécution Wine libre après 1 h")

    def __exit__(self, *exc):
        if self._fh:
            fcntl.flock(self._fh, fcntl.LOCK_UN)
            self._fh.close()


class PrefixManager:
    def __init__(self, work_dir: Path | str, wine: WineInfo | None = None, arch: str = "win64"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.wine = wine or wine_info()
        self.arch = arch
        self.xdg = self.work_dir / "xdg-runtime"
        self.xdg.mkdir(parents=True, exist_ok=True)
        os.chmod(self.xdg, 0o700)

    # -- environnement ----------------------------------------------------------------------------
    def base_env(self, prefix: Path, debug: str = "-all", overrides: dict[str, str] | None = None,
                 extra: dict[str, str] | None = None) -> dict[str, str]:
        env = dict(os.environ)
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        env["WINEPREFIX"] = str(prefix)
        env["WINEARCH"] = self.arch
        env["WINEDEBUG"] = debug
        env["XDG_RUNTIME_DIR"] = str(self.xdg)
        env["PATH"] = f"{self.wine.bin_dir}:{env.get('PATH', '')}"
        env["WINEDLLOVERRIDES"] = ";".join(f"{k}={v}" for k, v in (overrides or {}).items()) if overrides else "winemenubuilder.exe=d"
        if overrides and "winemenubuilder.exe" not in overrides:
            env["WINEDLLOVERRIDES"] += ";winemenubuilder.exe=d"
        if extra:
            env.update(extra)
        return env

    def _wine(self, prefix: Path, args: list[str], timeout: int = 300, debug: str = "-all",
              overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        env = self.base_env(prefix, debug=debug, overrides=overrides)
        return subprocess.run([f"{self.wine.bin_dir}/wine"] + args, env=env, capture_output=True, text=True, timeout=timeout)

    def wineserver(self, prefix: Path, flag: str, timeout: int = 120) -> None:
        env = self.base_env(prefix)
        try:
            subprocess.run([f"{self.wine.bin_dir}/wineserver", flag], env=env, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            pass

    # -- gabarit ----------------------------------------------------------------------------------
    @property
    def template_dir(self) -> Path:
        return self.work_dir / f"template-{self.wine.version}-{self.arch}"

    def ensure_template(self, log: Path | None = None) -> Path:
        tpl = self.template_dir
        marker = tpl / ".bdflab-template.json"
        if marker.exists():
            return tpl
        if tpl.exists():
            shutil.rmtree(tpl)
        tpl.mkdir(parents=True)
        t0 = time.time()
        env = self.base_env(tpl)
        subprocess.run([f"{self.wine.bin_dir}/wineboot", "-u"], env=env, capture_output=True, text=True, timeout=900)
        # réglages du laboratoire : pas de winedbg automatique (traces +seh suffisent, exécution
        # déterministe et plus rapide), pas de rapport de plantage interactif.
        self._wine(tpl, ["reg", "add", r"HKLM\Software\Microsoft\Windows NT\CurrentVersion\AeDebug", "/v", "Debugger", "/t", "REG_SZ", "/d", "false", "/f"])
        self._wine(tpl, ["reg", "add", r"HKCU\Software\Wine\WineDbg", "/v", "ShowCrashDialog", "/t", "REG_DWORD", "/d", "0", "/f"])
        self.wineserver(tpl, "-w")
        marker.write_text(json.dumps({"wine": self.wine.to_dict(), "arch": self.arch, "created_s": round(time.time() - t0, 1),
                                      "size_bytes": sum(p.stat().st_size for p in tpl.rglob("*") if p.is_file())}, indent=1))
        return tpl

    # -- préfixes jetables ------------------------------------------------------------------------
    def fresh_prefix(self, name: str) -> Path:
        tpl = self.ensure_template()
        dst = self.work_dir / "runs" / name / "prefix"
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        hardlinked = {"system32", "syswow64"}
        t0 = time.time()
        for item in tpl.iterdir():
            if item.name == "drive_c":
                (dst / "drive_c").mkdir()
                for sub in item.iterdir():
                    if sub.name == "windows":
                        (dst / "drive_c" / "windows").mkdir()
                        for w in sub.iterdir():
                            if w.name in hardlinked and w.is_dir():
                                subprocess.run(["cp", "-al", str(w), str(dst / "drive_c" / "windows" / w.name)], check=True)
                            else:
                                self._copy(w, dst / "drive_c" / "windows" / w.name)
                    else:
                        self._copy(sub, dst / "drive_c" / sub.name)
            else:
                self._copy(item, dst / item.name)
        (dst / ".bdflab-copy.json").write_text(json.dumps({"template": str(tpl), "copy_s": round(time.time() - t0, 2)}))
        return dst

    @staticmethod
    def _copy(src: Path, dst: Path) -> None:
        if src.is_symlink():
            os.symlink(os.readlink(src), dst)
        elif src.is_dir():
            shutil.copytree(src, dst, symlinks=True)
        else:
            shutil.copy2(src, dst)

    def destroy_prefix(self, prefix: Path) -> None:
        self.wineserver(prefix, "-k")
        time.sleep(0.3)
        shutil.rmtree(prefix, ignore_errors=True)


@dataclass
class RunResult:
    name: str
    command: list[str]
    cwd: str
    exit_code: int | None
    timed_out: bool
    wall_s: float
    cpu_user_s: float
    cpu_sys_s: float
    max_rss_kb_main: int
    peak_rss_kb_tree: int
    stdout_path: str
    stderr_path: str
    env_overrides: dict
    debug: str
    prefix: str
    started_at: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def stdout(self) -> str:
        return Path(self.stdout_path).read_text(encoding="utf-8", errors="replace")


class _TreeSampler(threading.Thread):
    """Échantillonne la RSS cumulée de tous les processus liés au préfixe (wineserver compris)."""

    def __init__(self, prefix: str, root_pid: int, interval: float = 0.25):
        super().__init__(daemon=True)
        self.prefix = prefix
        self.root_pid = root_pid
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()

    def run(self) -> None:
        if not psutil:
            return
        while not self._stop.is_set():
            total = 0
            try:
                root = psutil.Process(self.root_pid)
                procs = [root] + root.children(recursive=True)
            except psutil.Error:
                procs = []
            for p in psutil.process_iter(["name"]):
                try:
                    if p.info["name"] in {"wineserver", "wine", "wine64", "wine-preloader", "wine64-preloader", "start.exe",
                                          "services.exe", "explorer.exe", "winedevice.exe", "plugplay.exe", "svchost.exe",
                                          "rpcss.exe", "conhost.exe"} and p not in procs:
                        env = p.environ()
                        if env.get("WINEPREFIX") == self.prefix:
                            procs.append(p)
                except psutil.Error:
                    pass
            for p in procs:
                try:
                    total += p.memory_info().rss
                except psutil.Error:
                    pass
            self.peak = max(self.peak, total)
            self._stop.wait(self.interval)

    def stop(self) -> int:
        self._stop.set()
        self.join(timeout=2)
        return self.peak // 1024


def run_wine(pm: PrefixManager, prefix: Path, exe: Path, args: list[str], cwd: Path, log_dir: Path, name: str,
             timeout_s: int = 120, debug: str = DEFAULT_DEBUG, overrides: dict[str, str] | None = None,
             extra_env: dict[str, str] | None = None, relay_exclude: str | None = DEFAULT_RELAY_EXCLUDE) -> RunResult:
    """Lance ``exe args`` sous Wine dans ``prefix`` avec un délai maximal et des mesures."""
    log_dir = log_dir.resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{name}.stdout.txt"
    stderr_path = log_dir / f"{name}.wine.log"
    time_path = log_dir / f"{name}.time.txt"
    env = pm.base_env(prefix, debug=debug, overrides=overrides, extra=extra_env)
    if relay_exclude and "+relay" in debug:
        # RelayExclude est lu dans le registre du préfixe ; on l'écrit une fois par préfixe.
        marker = prefix / ".bdflab-relayexclude"
        if not marker.exists():
            pm._wine(prefix, ["reg", "add", r"HKCU\Software\Wine\Debug", "/v", "RelayExclude", "/t", "REG_SZ", "/d", relay_exclude, "/f"])
            marker.write_text(relay_exclude)
    cmd = ["/usr/bin/time", "-f", "%e %U %S %M", "-o", str(time_path), f"{pm.wine.bin_dir}/wine", str(exe)] + args
    notes: list[str] = []
    started = time.time()
    timed_out = False
    with open(stdout_path, "wb") as so, open(stderr_path, "wb") as se:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=so, stderr=se, stdin=subprocess.DEVNULL,
                                start_new_session=True)
        sampler = _TreeSampler(str(prefix), proc.pid)
        sampler.start()
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            notes.append(f"délai de {timeout_s} s dépassé : arrêt forcé (SIGTERM groupe, puis wineserver -k)")
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=10)
            pm.wineserver(prefix, "-k")
        peak_tree = sampler.stop()
    wall = time.time() - started
    exit_code: int | None = proc.returncode
    cpu_u = cpu_s = 0.0
    max_rss = 0
    if time_path.exists():
        try:
            parts = time_path.read_text().strip().split("\n")[-1].split()
            wall_t, cpu_u, cpu_s, max_rss = float(parts[0]), float(parts[1]), float(parts[2]), int(parts[3])
            wall = wall_t
        except Exception:
            notes.append("mesure GNU time illisible")
    # /usr/bin/time renvoie le code du programme (ou 124+ en cas de signal)
    return RunResult(name=name, command=cmd[5:], cwd=str(cwd), exit_code=exit_code, timed_out=timed_out,
                     wall_s=round(wall, 3), cpu_user_s=cpu_u, cpu_sys_s=cpu_s, max_rss_kb_main=max_rss,
                     peak_rss_kb_tree=peak_tree, stdout_path=str(stdout_path), stderr_path=str(stderr_path),
                     env_overrides=dict(overrides or {}), debug=debug, prefix=str(prefix), started_at=started, notes=notes)
