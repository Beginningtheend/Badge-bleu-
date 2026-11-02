"""Accès à la base de connaissances Wine construite par ``bdflab.knowledge.build_wine_db``.

Résout un import ``(dll, fonction)`` vers un statut dans la version de Wine analysée :

``implemented``   export présent et aucun FIXME « stub » dans son implémentation ;
``semi-stub``     export présent mais implémentation marquée FIXME stub / semi-stub / non implémenté ;
``stub``          export déclaré ``@ stub`` dans le .spec (appel → EXCEPTION_WINE_STUB, 0x80000100) ;
``export-absent`` DLL fournie par Wine mais export absent (le chargeur Wine installe un stub qui lève
                  aussi EXCEPTION_WINE_STUB à l'appel, cf. dlls/ntdll/loader.c allocate_stub) ;
``dll-missing``   DLL non fournie par Wine (import statique → échec du chargement du programme) ;
``forward-broken`` forward vers une cible inconnue.
"""
from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "wine-11.0"

# DLL dont Wine impose la version builtin (dlls/ntdll/loadorder.c : « always builtin ») — on ne peut pas
# les remplacer par une DLL native via WINEDLLOVERRIDES. Liste conservatrice.
ALWAYS_BUILTIN = {
    "ntdll", "kernel32", "kernelbase", "win32u", "user32", "gdi32", "advapi32", "sechost", "msvcrt",
    "ucrtbase", "ntoskrnl.exe", "winecrt0", "wow64", "wow64win", "wow64cpu", "xtajit64", "explorer.exe",
    "winebus.sys", "wineusb.sys", "winehid.sys", "winexinput.sys", "winex11.drv", "winewayland.drv",
    "wineps.drv", "winemac.drv", "wineandroid.drv", "winevulkan", "opengl32", "winspool.drv", "mountmgr.sys",
}


def norm_dll(name: str) -> str:
    """Normalise un nom de DLL : minuscules, sans chemin, sans extension .dll."""
    n = name.strip().lower().replace("\\", "/").rsplit("/", 1)[-1]
    if n.endswith(".dll"):
        n = n[:-4]
    return n


@dataclass
class Resolution:
    dll: str
    func: str
    status: str
    chain: list[str] = field(default_factory=list)
    entry: dict | None = None
    semistub: dict | None = None
    prototype: dict | None = None
    notes: list[str] = field(default_factory=list)
    final_dll: str = ""
    final_func: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def problematic(self) -> bool:
        return self.status in {"stub", "export-absent", "dll-missing", "forward-broken", "semi-stub"}

    @property
    def crashes_on_call(self) -> bool:
        """Vrai si l'appel lève EXCEPTION_WINE_STUB (stub explicite ou export absent)."""
        return self.status in {"stub", "export-absent", "forward-broken"}


class WineDB:
    def __init__(self, data_dir: Path | str = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.meta = json.loads((self.data_dir / "meta.json").read_text())
        with gzip.open(self.data_dir / "exports.json.gz", "rt", encoding="utf-8") as fh:
            self.exports: dict[str, dict[str, dict]] = json.load(fh)
        self.semistubs: dict[str, dict[str, dict]] = json.loads((self.data_dir / "semistubs.json").read_text())
        with gzip.open(self.data_dir / "prototypes.json.gz", "rt", encoding="utf-8") as fh:
            self.prototypes: dict[str, dict] = json.load(fh)
        self.builtins: dict[str, dict[str, dict]] = json.loads((self.data_dir / "builtins.json").read_text())
        apisets_path = self.data_dir / "apisets.json"
        self.apisets: dict[str, str] = json.loads(apisets_path.read_text()) if apisets_path.exists() else {}

    # -- inventaire -------------------------------------------------------------------------------
    @property
    def wine_version(self) -> str:
        return self.meta.get("wine_version", "unknown")

    def dll_known(self, dll: str, arch: str = "x86_64") -> bool:
        d = norm_dll(dll)
        if d in self.exports:
            return True
        return (d + ".dll") in self.builtins.get(arch, {}) or d in self.builtins.get(arch, {})

    def dll_has_unix_part(self, dll: str, arch: str = "x86_64") -> bool:
        d = norm_dll(dll)
        info = self.builtins.get(arch, {}).get(d + ".dll") or self.builtins.get(arch, {}).get(d)
        return bool(info and info.get("unix"))

    def dll_builtin_size(self, dll: str, arch: str = "x86_64") -> int:
        d = norm_dll(dll)
        info = self.builtins.get(arch, {}).get(d + ".dll") or self.builtins.get(arch, {}).get(d) or {}
        return int(info.get("size", 0))

    def resolve_apiset(self, dll: str) -> str | None:
        d = norm_dll(dll)
        if not (d.startswith("api-ms-win-") or d.startswith("ext-ms-win-")):
            return None
        target = self.apisets.get(d)
        if target:
            return norm_dll(target)
        # tolérance sur le numéro de version mineur : api-ms-win-core-x-l1-1-2 → l1-1-*
        m = re.match(r"^(.*-l\d+-\d+)-\d+$", d)
        if m:
            prefix = m.group(1)
            for k, v in self.apisets.items():
                if k.startswith(prefix + "-"):
                    return norm_dll(v)
        return None

    def entry(self, dll: str, func: str, arch: str = "x86_64") -> dict | None:
        d = norm_dll(dll)
        table = self.exports.get(d)
        if not table:
            return None
        e = table.get(func)
        if e is None:
            return None
        if e.get("t") == "absent":
            return e
        cands = [e] + list(e.get("alt", []))
        for c in cands:
            archs = c.get("arch")
            if archs is None or arch in archs:
                return c
        return {"t": "absent", "note": "arch-restricted", "archs": [c.get("arch") for c in cands]}

    def semistub(self, dll: str, handler: str) -> dict | None:
        return self.semistubs.get(norm_dll(dll), {}).get(handler)

    def prototype(self, func: str) -> dict | None:
        return self.prototypes.get(func)

    def stubs_of(self, dll: str, arch: str = "x86_64") -> list[str]:
        d = norm_dll(dll)
        out = []
        for name, e in self.exports.get(d, {}).items():
            ee = self.entry(d, name, arch)
            if ee and ee.get("t") == "stub":
                out.append(name)
        return sorted(out)

    # -- résolution -------------------------------------------------------------------------------
    def resolve(self, dll: str, func: str, arch: str = "x86_64", _depth: int = 0, _chain: list[str] | None = None) -> Resolution:
        chain = list(_chain or [])
        d = norm_dll(dll)
        chain.append(f"{d}.{func}")
        res = Resolution(dll=d, func=func, status="unknown", chain=chain, final_dll=d, final_func=func)
        target = self.resolve_apiset(d)
        if target:
            res.notes.append(f"api-set {d} → {target} (apisetschema)")
            d = target
            chain.append(f"{d}.{func}")
            res.final_dll = d
        elif d.startswith("api-ms-win-") or d.startswith("ext-ms-win-"):
            res.notes.append("api-set inconnu de apisetschema")
        if not self.dll_known(d, arch):
            res.status = "dll-missing"
            res.prototype = self.prototype(func)
            return res
        e = self.entry(d, func, arch)
        res.entry = e
        res.prototype = self.prototype(func)
        if e is None or e.get("t") == "absent":
            res.status = "export-absent"
            if e and e.get("note"):
                res.notes.append(str(e.get("note")))
            return res
        t = e.get("t")
        if t == "stub":
            res.status = "stub"
            return res
        if e.get("f") and _depth < 8:
            fdll, _, ffunc = e["f"].partition(".")
            sub = self.resolve(fdll, ffunc, arch, _depth + 1, chain)
            sub.dll, sub.func = res.dll, res.func
            sub.notes = res.notes + [f"forward {d}.{func} → {e['f']}"] + sub.notes
            sub.prototype = sub.prototype or res.prototype
            if sub.status == "dll-missing" or sub.status == "export-absent":
                sub.status = "forward-broken"
            return sub
        flags = e.get("fl", [])
        if "-import" in flags and _depth < 8:
            # export implémenté en important la fonction d'une DLL de base (kernel32 → kernelbase, etc.)
            for imp in ("kernelbase", "ntdll", "kernel32"):
                if imp == d:
                    continue
                ie = self.entry(imp, e.get("h") or func, arch)
                if ie and ie.get("t") != "absent":
                    sub = self.resolve(imp, e.get("h") or func, arch, _depth + 1, chain)
                    sub.dll, sub.func = res.dll, res.func
                    sub.notes = res.notes + [f"-import : {d}.{func} fourni par {imp}"] + sub.notes
                    sub.prototype = sub.prototype or res.prototype
                    return sub
            res.notes.append("-import sans cible identifiée")
        handler = e.get("h") or func
        ss = self.semistub(d, handler)
        if ss is None and handler != func:
            ss = self.semistub(d, func)
        if ss:
            res.semistub = ss
            res.status = "semi-stub"
            res.notes.append(f"FIXME {ss.get('kind')} : {ss.get('msg', '')[:80]} ({ss.get('file')}:{ss.get('line')})")
            return res
        if t in {"extern", "equiv"}:
            res.notes.append(f"export de type {t} (donnée)")
        res.status = "implemented"
        return res


@lru_cache(maxsize=4)
def load_db(data_dir: str | None = None) -> WineDB:
    return WineDB(Path(data_dir) if data_dir else DEFAULT_DATA_DIR)
