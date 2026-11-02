"""Analyse des journaux Wine (``WINEDEBUG=+relay,+tid,+timestamp,+seh,warn+module,+loaddll``).

Repère : appels à des fonctions non implémentées (EXCEPTION_WINE_STUB), imports sans implémentation,
DLL introuvables (statiques et dynamiques), exceptions, FIXME « stub », erreurs, derniers appels
relay avant une exception fatale.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, asdict
from pathlib import Path

PREFIX = r"^(?:(?P<ts>\d+\.\d+):)?(?P<tid>[0-9a-f]{4}):"
RE_CALL = re.compile(PREFIX + r"Call (?P<mod>[\w.\-]+)\.(?P<func>[\w@?$]+)\((?P<args>.*)\) ret=(?P<ret>[0-9a-fA-F]+)\s*$")
RE_RET = re.compile(PREFIX + r"Ret  (?P<mod>[\w.\-]+)\.(?P<func>[\w@?$]+)\(\) retval=(?P<retval>[0-9a-fA-F]+) ret=(?P<ret>[0-9a-fA-F]+)\s*$")
RE_CALL_PROC = re.compile(PREFIX + r"Call (?P<what>process|thread|TLS callback|LDR notification|PE DLL|window proc)\b")
RE_MSG = re.compile(PREFIX + r"(?P<cls>trace|warn|err|fixme):(?P<chan>\w+):(?P<func>\w+) ?(?P<msg>.*)$")
RE_UNIMPL = re.compile(r"^wine: Call from (?P<addr>[0-9A-Fa-f]+) to unimplemented function (?P<mod>[\w.\-]+)\.(?P<func>[\w@?$#]+), aborting")
RE_UNIMPL2 = re.compile(r"^wine: Unimplemented function (?P<mod>[\w.\-]+)\.(?P<func>[\w@?$#]+) called at address (?P<addr>[0-9A-Fa-f]+) \(thread (?P<tid>[0-9a-f]+)\)")
RE_UNHANDLED = re.compile(r"^wine: Unhandled (?P<what>.+?) (?:\(0x(?P<code>[0-9a-f]+)\) )?(?:on (?P<access>\w+) access to (?P<target>[0-9A-Fa-f]+) )?at address (?P<addr>[0-9A-Fa-f]+) \(thread (?P<tid>[0-9a-f]+)\)")
RE_UNHANDLED_EXC = re.compile(r"^wine: Unhandled exception 0x(?P<code>[0-9a-f]+) in thread (?P<tid>[0-9a-f]+) at address (?P<addr>[0-9A-Fa-f]+)")
RE_SEH = re.compile(r"code=(?P<code>[0-9a-f]+)(?: \((?P<name>\w+)\))? flags=(?P<flags>\d+) addr=(?P<addr>[0-9A-Fa-f]+)")
RE_NOIMPL = re.compile(r"No implementation for (?P<mod>[\w.\-]+)\.(?P<func>[\w@?$#]+) imported from L\"(?P<from>[^\"]+)\", setting to (?P<addr>[0-9A-Fa-f]+)")
RE_LIBNOTFOUND = re.compile(r"Library (?P<lib>[\w.\-]+) \(which is needed by L\"(?P<from>[^\"]+)\"\) not found")
RE_LOADFAIL = re.compile(r"Importing dlls for L\"(?P<exe>[^\"]+)\" failed, status (?P<status>[0-9a-f]+)")
RE_LOADDLL = re.compile(r"Loaded L\"(?P<path>[^\"]+)\" at (?P<addr>[0-9A-Fa-f]+): (?P<kind>native|builtin|PE builtin)")
RE_WSTR_ARG = re.compile(r'L"([^"]*)"')

LOADLIB_FUNCS = {"LoadLibraryW", "LoadLibraryA", "LoadLibraryExW", "LoadLibraryExA", "LdrLoadDll"}


@dataclass
class StubCall:
    module: str
    func: str
    address: str
    tid: str
    line_no: int
    context: list[str] = field(default_factory=list)  # derniers appels relay du même thread


@dataclass
class TraceSummary:
    path: str
    lines: int
    relay_calls: int
    stub_calls: list[StubCall]
    missing_impl_imports: list[dict]
    missing_libraries: list[dict]
    import_failures: list[dict]
    dynamic_load_failures: list[dict]
    exceptions: list[dict]
    unhandled: list[dict]
    fixme_stubs: list[dict]
    errs: list[dict]
    loaded_modules: list[dict]
    calls_by_function: dict
    fatal: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def problem_functions(self) -> list[tuple[str, str]]:
        """Fonctions impliquées dans une panne : (module, fonction)."""
        out: list[tuple[str, str]] = []
        for s in self.stub_calls:
            k = (s.module.lower().removesuffix(".dll"), s.func)
            if k not in out:
                out.append(k)
        return out


def parse_wine_log(path: Path | str, max_context: int = 12, keep_calls_by_function: int = 400) -> TraceSummary:
    path = Path(path)
    stub_calls: list[StubCall] = []
    missing_impl: list[dict] = []
    missing_libs: list[dict] = []
    import_failures: list[dict] = []
    dyn_fail: list[dict] = []
    exceptions: list[dict] = []
    unhandled: list[dict] = []
    fixmes: Counter = Counter()
    fixme_samples: dict[str, str] = {}
    errs: Counter = Counter()
    err_samples: dict[str, str] = {}
    loaded: list[dict] = []
    calls_by_func: Counter = Counter()
    relay_calls = 0
    last_calls: dict[str, deque] = defaultdict(lambda: deque(maxlen=max_context))
    pending_loadlib: dict[str, list[str]] = defaultdict(list)  # tid -> pile des args L"..." des LoadLibrary en cours
    n = 0
    fatal = False
    notes: list[str] = []
    seen_unimpl: set[tuple[str, str, str]] = set()

    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            m = RE_CALL.match(line)
            if m:
                relay_calls += 1
                key = f"{m.group('mod')}.{m.group('func')}"
                calls_by_func[key] += 1
                last_calls[m.group("tid")].append(f"{n}: {line[:220]}")
                if m.group("func") in LOADLIB_FUNCS:
                    wargs = RE_WSTR_ARG.findall(m.group("args"))
                    pending_loadlib[m.group("tid")].append(wargs[0] if wargs else m.group("args")[:80])
                continue
            m = RE_RET.match(line)
            if m:
                if m.group("func") in LOADLIB_FUNCS and pending_loadlib.get(m.group("tid")):
                    arg = pending_loadlib[m.group("tid")].pop()
                    if int(m.group("retval"), 16) == 0:
                        dyn_fail.append({"func": m.group("func"), "library": arg, "tid": m.group("tid"), "line": n})
                continue
            m = RE_UNIMPL.match(line) or RE_UNIMPL2.match(line)
            if m:
                key = (m.group("mod"), m.group("func"), m.group("addr"))
                if key not in seen_unimpl:
                    seen_unimpl.add(key)
                    tid = m.groupdict().get("tid") or ""
                    # contexte : le thread le plus récent si inconnu
                    ctx_tid = tid or (max(last_calls, key=lambda t: len(last_calls[t])) if last_calls else "")
                    stub_calls.append(StubCall(module=m.group("mod"), func=m.group("func"), address=m.group("addr"),
                                               tid=ctx_tid, line_no=n, context=list(last_calls.get(ctx_tid, []))))
                fatal = True
                continue
            m = RE_UNHANDLED.match(line) or RE_UNHANDLED_EXC.match(line)
            if m:
                unhandled.append({**{k: v for k, v in m.groupdict().items() if v}, "line": n})
                fatal = True
                continue
            m = RE_MSG.match(line)
            if m:
                cls, chan, func, msg = m.group("cls"), m.group("chan"), m.group("func"), m.group("msg")
                if chan == "seh" and (func == "dispatch_exception" or msg.startswith("code=")):
                    sm = RE_SEH.search(msg)
                    if sm:
                        exceptions.append({"code": sm.group("code"), "name": sm.group("name") or "", "flags": int(sm.group("flags")),
                                           "addr": sm.group("addr"), "tid": m.group("tid"), "line": n})
                    continue
                if chan in ("module", "loaddll"):
                    mm = RE_NOIMPL.search(msg)
                    if mm:
                        missing_impl.append({**mm.groupdict(), "line": n})
                        continue
                    mm = RE_LIBNOTFOUND.search(msg)
                    if mm:
                        missing_libs.append({**mm.groupdict(), "line": n})
                        fatal = True
                        continue
                    mm = RE_LOADFAIL.search(msg)
                    if mm:
                        import_failures.append({**mm.groupdict(), "line": n})
                        fatal = True
                        continue
                    mm = RE_LOADDLL.search(msg)
                    if mm:
                        loaded.append({"path": mm.group("path"), "kind": mm.group("kind"), "addr": mm.group("addr")})
                        continue
                if cls == "fixme":
                    key = f"{chan}:{func}"
                    fixmes[key] += 1
                    fixme_samples.setdefault(key, msg[:200])
                elif cls == "err":
                    key = f"{chan}:{func}"
                    errs[key] += 1
                    err_samples.setdefault(key, msg[:200])
                continue
    fixme_list = [{"where": k, "count": c, "sample": fixme_samples[k], "stub": bool(re.search(r"\bstub", fixme_samples[k], re.I))}
                  for k, c in fixmes.most_common()]
    err_list = [{"where": k, "count": c, "sample": err_samples[k]} for k, c in errs.most_common()]
    # exceptions fatales = EXCEPTION_WINE_STUB (80000100) ou non continuables suivies d'un « Unhandled »
    if any(e["code"].lower() == "80000100" for e in exceptions):
        fatal = True
    top_calls = dict(calls_by_func.most_common(keep_calls_by_function))
    return TraceSummary(path=str(path), lines=n, relay_calls=relay_calls, stub_calls=stub_calls, missing_impl_imports=missing_impl,
                        missing_libraries=missing_libs, import_failures=import_failures, dynamic_load_failures=dyn_fail,
                        exceptions=exceptions, unhandled=unhandled, fixme_stubs=fixme_list, errs=err_list, loaded_modules=loaded,
                        calls_by_function=top_calls, fatal=fatal, notes=notes)


def parse_app_stdout(path: Path | str, marker: str = "BDFEDIT|") -> list[dict]:
    """Lit les lignes de protocole « MARKER|EVENT|k=v|... » émises par le programme de test."""
    events: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(marker):
            continue
        parts = line.split("|")
        ev = {"event": parts[1] if len(parts) > 1 else ""}
        for p in parts[2:]:
            k, _, v = p.partition("=")
            ev[k] = v
        events.append(ev)
    return events
