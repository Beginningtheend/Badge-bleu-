#!/usr/bin/env python3
"""Construit la base de connaissances Wine utilisée par le labo.

Entrées (outils existants, pas d'analyseur maison) :
  * l'arbre source Wine (``dlls/*/*.spec``, ``dlls/*/*.c``, ``include/*.h``) ;
  * une installation Wine (``lib/wine/x86_64-windows/*.dll`` et ``x86_64-unix/*.so``).

Sorties, dans ``data/wine-<version>/`` :
  * ``meta.json``        : version, sha256 du tarball source, compteurs ;
  * ``exports.json.gz``  : pour chaque DLL, chaque export du .spec (type, args, forward, arch) ;
                           les lignes ``# @ stub X`` (exports volontairement absents) sont gardées
                           avec le type ``absent`` ;
  * ``semistubs.json``   : fonctions dont le corps C contient un ``FIXME("... stub")`` ou équivalent ;
  * ``prototypes.json.gz`` : prototypes extraits des en-têtes publics (type de retour, paramètres) ;
  * ``builtins.json``    : DLL fournies par l'installation Wine, avec ou sans partie Unix.

Usage :
  python3 -m bdflab.knowledge.build_wine_db --source <wine-src> --install /opt/wine-stable \
          --out data/wine-11.0 [--tarball-sha256 <hex>]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# .spec
# ---------------------------------------------------------------------------

SPEC_LINE = re.compile(
    r"^\s*(?P<ord>@|\d+)\s+"
    r"(?P<type>stdcall|cdecl|varargs|thiscall|fastcall|pascal|stub|extern|equiv)\s*"
    r"(?P<flags>(?:-[\w=!,.\-]+\s+)*)"
    r"(?P<name>[^\s(]+)\s*"
    r"(?:\((?P<args>[^)]*)\))?\s*"
    r"(?P<handler>\S+)?\s*$"
)
SPEC_COMMENTED_STUB = re.compile(r"^\s*#\s*@\s+stub\s+(?P<name>\S+)")

WIN32_ARCHS = {"i386", "arm"}
WIN64_ARCHS = {"x86_64", "arm64", "arm64ec"}
ALL_ARCHS = WIN32_ARCHS | WIN64_ARCHS


def parse_arch_flags(flags: list[str]) -> set[str] | None:
    """Retourne l'ensemble des architectures où l'entrée existe, ou None si toutes."""
    archs: set[str] | None = None
    for fl in flags:
        if fl == "-i386":
            archs = (archs or set()) | {"i386"}
        elif fl == "-win32":
            archs = (archs or set()) | WIN32_ARCHS
        elif fl == "-win64":
            archs = (archs or set()) | WIN64_ARCHS
        elif fl.startswith("-arch="):
            spec = fl[len("-arch="):]
            neg = spec.startswith("!")
            if neg:
                spec = spec[1:]
            vals: set[str] = set()
            for v in spec.split(","):
                v = v.strip()
                if v == "win32":
                    vals |= WIN32_ARCHS
                elif v == "win64":
                    vals |= WIN64_ARCHS
                elif v:
                    vals.add(v)
            archs = (ALL_ARCHS - vals) if neg else ((archs or set()) | vals)
    return archs


def parse_spec(path: Path) -> dict[str, dict]:
    """Analyse un fichier .spec. Retourne {export_name: entry}."""
    out: dict[str, dict] = {}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            m = SPEC_COMMENTED_STUB.match(line)
            if m:
                name = m.group("name")
                out.setdefault(name, {"t": "absent", "line": lineno, "note": "commented stub"})
                continue
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = SPEC_LINE.match(line)
            if not m:
                continue
            flags = m.group("flags").split()
            entry: dict = {"t": m.group("type"), "line": lineno}
            if m.group("ord") != "@":
                entry["o"] = int(m.group("ord"))
            if m.group("args") is not None:
                entry["a"] = m.group("args").split()
            handler = m.group("handler")
            name = m.group("name")
            if handler and handler != name:
                if "." in handler and not handler.startswith("."):
                    entry["f"] = handler  # forward dll.func
                else:
                    entry["h"] = handler
            if flags:
                entry["fl"] = flags
                archs = parse_arch_flags(flags)
                if archs is not None:
                    entry["arch"] = sorted(archs)
            # Un export déjà vu avec une autre arch (ex. -arch=i386 puis -arch=win64) : garder les deux.
            if name in out and out[name].get("t") != "absent":
                prev = out[name]
                prev.setdefault("alt", []).append(entry)
            else:
                out[name] = entry
    return out


APISET_LINE = re.compile(r"^\s*apiset\s+(?P<name>[\w.\-]+)\s*=\s*(?P<target>[\w.\-]+)\s*$")


def parse_apisets(spec: Path) -> dict[str, str]:
    """Analyse dlls/apisetschema/apisetschema.spec : « apiset api-ms-win-x = kernelbase.dll »."""
    out: dict[str, str] = {}
    if not spec.exists():
        return out
    for raw in spec.read_text(encoding="utf-8", errors="replace").splitlines():
        m = APISET_LINE.match(raw)
        if m:
            out[m.group("name").lower()] = m.group("target").lower()
    return out


# ---------------------------------------------------------------------------
# semi-stubs (FIXME dans les sources C)
# ---------------------------------------------------------------------------

FUNC_HEADER = re.compile(
    r"^(?!static\b)(?!extern\b)(?!typedef\b)[A-Za-z_][\w\s\*]*?\b"
    r"(?:WINAPI|CDECL|__cdecl|WINAPIV|APIENTRY|NTAPI|STDCALL|__thiscall|THISCALL|__fastcall|FASTCALL|WINAPIV)\b"
    r"[\w\s\*]*?\b(?P<name>[A-Za-z_]\w*)\s*\("
)
FIXME_CALL = re.compile(r"\bFIXME(?:_\(\s*\w+\s*\))?\s*\(")
STRING_LIT = re.compile(r'"((?:[^"\\]|\\.)*)"')
DECLARED_ABSENCE = re.compile(
    r"ERROR_CALL_NOT_IMPLEMENTED|E_NOTIMPL|STATUS_NOT_IMPLEMENTED|STATUS_NOT_SUPPORTED|"
    r"ERROR_NOT_SUPPORTED|ERROR_INVALID_FUNCTION|HRESULT_FROM_WIN32\(\s*ERROR_CALL_NOT_IMPLEMENTED"
)


def scan_c_file(path: Path) -> dict[str, dict]:
    """Attribue chaque FIXME à la fonction englobante (heuristique sur le style Wine).

    Retourne {symbol: {kind, msg, declared_absence, file, line}} pour les fonctions dont
    un FIXME parle de « stub » (stub complet ou semi-stub) ou de fonctionnalité non implémentée.
    """
    results: dict[str, dict] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return results
    lines = text.split("\n")
    current: str | None = None
    current_start = 0
    body_lines: list[str] = []

    def flush(name: str | None, body: list[str], start: int) -> None:
        if not name or not body:
            return
        body_text = "\n".join(body)
        kinds: list[tuple[str, str, int]] = []
        for m in FIXME_CALL.finditer(body_text):
            tail = body_text[m.end(): m.end() + 400]
            sm = STRING_LIT.search(tail)
            msg = sm.group(1) if sm else ""
            low = msg.lower()
            if "semi-stub" in low or "semi stub" in low or "semistub" in low or "partial" in low:
                kind = "semi-stub"
            elif re.search(r"\bstub", low):
                kind = "stub"
            elif "not implemented" in low or "unimplemented" in low or "not supported" in low or "unsupported" in low:
                kind = "fixme-unimplemented"
            else:
                continue
            line_no = start + body_text[: m.start()].count("\n")
            kinds.append((kind, msg, line_no))
        if not kinds:
            return
        # priorité : stub > semi-stub > fixme-unimplemented
        order = {"stub": 0, "semi-stub": 1, "fixme-unimplemented": 2}
        kinds.sort(key=lambda k: order[k[0]])
        kind, msg, line_no = kinds[0]
        results[name] = {
            "kind": kind,
            "msg": msg[:160],
            "declared_absence": bool(DECLARED_ABSENCE.search(body_text)),
            "file": str(path),
            "line": line_no,
            "n_fixme": len(kinds),
        }

    for i, line in enumerate(lines, 1):
        hm = FUNC_HEADER.match(line)
        if hm and not line.rstrip().endswith(";"):
            flush(current, body_lines, current_start)
            current = hm.group("name")
            current_start = i
            body_lines = [line]
            continue
        if current is not None:
            body_lines.append(line)
            if line.startswith("}"):
                flush(current, body_lines, current_start)
                current = None
                body_lines = []
    flush(current, body_lines, current_start)
    return results


# ---------------------------------------------------------------------------
# prototypes (en-têtes publics)
# ---------------------------------------------------------------------------

COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
CALLCONV = r"(?:WINAPI|APIENTRY|NTAPI|WINAPIV|CDECL|__cdecl|STDAPICALLTYPE|STDMETHODCALLTYPE|SEC_ENTRY|WSAAPI|PASCAL|NTSYSAPI)"
LINKAGE_MACROS = {
    "WINBASEAPI", "WINUSERAPI", "WINGDIAPI", "WINADVAPI", "WINSHELLAPI", "WINCOMMCTRLAPI", "WINCOMMDLGAPI",
    "WINMMAPI", "WINSOCK_API_LINKAGE", "DECLSPEC_NORETURN", "DECLSPEC_HIDDEN", "DECLSPEC_HOTPATCH",
    "NTSYSAPI", "NTSYSCALLAPI", "CREDUIAPI", "WINPATHCCHAPI", "WINHTTPAPI", "WINSETUPAPI", "WINPRINTAPI",
    "SECURITY_STATUS_API", "DECLSPEC_IMPORT", "DECLSPEC_EXPORT", "extern", "IMAGEAPI", "WINTRUSTAPI",
    "WINEDBGAPI", "DNSAPI", "USERENVAPI", "WINOLEAPI", "WINOLEAUTAPI", "LWSTDAPI", "SHSTDAPI", "PSSTDAPI",
    "THEMEAPI", "DWMAPI", "BOOLAPI", "URLCACHEAPI", "INTERNETAPI", "WINGLAPI", "STDAPI", "WINSCARDAPI",
    "BOOLAPI_", "D3DX", "CONST",
}
# macros de type « STDAPI_(T) », « WINOLEAPI_(T) » : le retour est T ; sans parenthèses : HRESULT
HRESULT_MACROS = {"STDAPI", "WINOLEAPI", "WINOLEAUTAPI", "LWSTDAPI", "SHSTDAPI", "PSSTDAPI", "THEMEAPI", "DWMAPI",
                  "URLCACHEAPI", "INTERNETAPI", "STDMETHODIMP"}
TYPED_MACRO = re.compile(r"\b(STDAPI_|WINOLEAPI_|WINOLEAUTAPI_|LWSTDAPI_|SHSTDAPI_|PSSTDAPI_|THEMEAPI_|BOOLAPI_|URLCACHEAPI_|INTERNETAPI_)\(\s*([^()]*?)\s*\)")

PROTO_RE = re.compile(
    r"(?P<pre>[A-Za-z_][\w\s\*(),]*?)\b(?P<cc>" + CALLCONV + r")\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>(?:[^()]|\([^()]*\))*)\)\s*;"
)
MACRO_PROTO_RE = re.compile(
    r"\b(?P<macro>STDAPI|WINOLEAPI|WINOLEAUTAPI|LWSTDAPI|SHSTDAPI|PSSTDAPI|THEMEAPI|DWMAPI|BOOLAPI|URLCACHEAPI|INTERNETAPI)"
    r"(?:_\(\s*(?P<ret>[^()]*?)\s*\))?\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<params>(?:[^()]|\([^()]*\))*)\)\s*;"
)


def split_params(params: str) -> list[list[str]]:
    params = params.strip()
    if not params or params == "void" or params.upper() == "VOID":
        return []
    out: list[list[str]] = []
    depth = 0
    cur = ""
    for ch in params:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    result: list[list[str]] = []
    for p in out:
        p = re.sub(r"\s+", " ", p).strip()
        if p == "...":
            result.append(["...", ""])
            continue
        # séparer le nom du paramètre (dernier identifiant, s'il n'est pas un mot-clé de type)
        m = re.match(r"^(.*?)[\s\*]([A-Za-z_]\w*)\s*(\[[^\]]*\])?$", p)
        if m and m.group(2) not in {"int", "char", "long", "short", "void", "double", "float", "unsigned",
                                     "const", "struct", "union", "enum", "signed"} and not re.match(r"^[A-Z_][A-Z0-9_]*$", m.group(2)) \
                and not p.endswith("*") and len(m.group(1).strip()) > 0:
            typ = m.group(1).strip() + ("*" if p[len(m.group(1))] == "*" else "")
            typ = re.sub(r"\s+", " ", typ).strip()
            result.append([typ, m.group(2) + (m.group(3) or "")])
        else:
            result.append([p, ""])
    return result


def clean_ret(pre: str) -> str:
    toks = [t for t in re.split(r"\s+", pre.strip()) if t]
    toks = [t for t in toks if t not in LINKAGE_MACROS and not t.startswith("DECLSPEC_") and t not in {'"C"'}
            and not re.fullmatch(r"[A-Z][A-Z0-9_]*API", t) and not re.fullmatch(r"[A-Z][A-Z0-9_]*API_?\(.*\)", t)]
    ret = " ".join(toks).strip()
    ret = ret.replace(" *", "*").replace("* ", "*")
    return ret


def scan_headers(include_dir: Path) -> dict[str, dict]:
    protos: dict[str, dict] = {}
    for hdr in sorted(include_dir.glob("*.h")):
        try:
            text = hdr.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = COMMENT_RE.sub(" ", text)
        # supprimer les directives préprocesseur (lignes #...)
        text = re.sub(r"^\s*#.*$", " ", text, flags=re.M)
        # prototypes avec macro de retour (STDAPI etc.)
        for m in MACRO_PROTO_RE.finditer(text):
            name = m.group("name")
            macro = m.group("macro")
            ret = m.group("ret")
            if ret is None:
                ret = "BOOL" if macro == "BOOLAPI" else "HRESULT"
            protos.setdefault(name, {"ret": clean_ret(ret), "params": split_params(m.group("params")), "hdr": hdr.name,
                                     "cc": "WINAPI"})
        for m in PROTO_RE.finditer(text):
            name = m.group("name")
            pre = m.group("pre")
            # ne garder que la dernière « phrase » du préfixe (après ; { } ou retour à la ligne vide)
            pre = re.split(r"[;{}]", pre)[-1]
            pre_lines = [l for l in pre.split("\n") if l.strip()]
            # le type de retour est sur la/les dernières lignes ; on prend tout après la dernière ligne vide
            pre = " ".join(pre_lines[-2:]) if pre_lines else ""
            ret = clean_ret(pre)
            if not ret or ret.endswith(",") or "(" in ret or ")" in ret:
                continue
            if name in protos and protos[name].get("hdr") != hdr.name:
                continue
            protos[name] = {"ret": ret, "params": split_params(m.group("params")), "hdr": hdr.name,
                            "cc": m.group("cc")}
    return protos


# ---------------------------------------------------------------------------
# installation Wine
# ---------------------------------------------------------------------------

def scan_install(install: Path) -> dict:
    out: dict = {}
    for arch in ("x86_64", "i386", "aarch64"):
        pe_dir = install / "lib" / "wine" / f"{arch}-windows"
        unix_dir = install / "lib" / "wine" / f"{arch}-unix"
        if not pe_dir.is_dir():
            continue
        dlls: dict[str, dict] = {}
        for p in sorted(pe_dir.iterdir()):
            if p.suffix.lower() not in {".dll", ".exe", ".drv", ".ocx", ".acm", ".cpl", ".ds", ".sys", ".tlb", ".vxd"}:
                continue
            name = p.name.lower()
            stem = p.stem.lower()
            dlls[name] = {
                "size": p.stat().st_size,
                "unix": (unix_dir / f"{stem}.so").exists(),
            }
        out[arch] = dlls
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, type=Path, help="arbre source Wine (contenant dlls/ et include/)")
    ap.add_argument("--install", type=Path, default=Path("/opt/wine-stable"), help="préfixe d'installation Wine")
    ap.add_argument("--out", required=True, type=Path, help="répertoire de sortie (data/wine-<ver>)")
    ap.add_argument("--tarball-sha256", default="", help="sha256 du tarball source (traçabilité)")
    args = ap.parse_args(argv)

    src: Path = args.source
    version = (src / "VERSION").read_text().strip().replace("Wine version ", "") if (src / "VERSION").exists() else "unknown"
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    # 1. specs
    exports: dict[str, dict[str, dict]] = {}
    spec_files = sorted((src / "dlls").glob("*/*.spec"))
    for spec in spec_files:
        dll = spec.stem.lower()
        entries = parse_spec(spec)
        if dll in exports:
            exports[dll].update(entries)
        else:
            exports[dll] = entries
    # 2. semi-stubs
    semistubs: dict[str, dict[str, dict]] = {}
    for dll_dir in sorted((src / "dlls").iterdir()):
        if not dll_dir.is_dir():
            continue
        found: dict[str, dict] = {}
        for cfile in sorted(dll_dir.rglob("*.c")):
            if "tests" in cfile.parts:
                continue
            for sym, info in scan_c_file(cfile).items():
                info["file"] = str(cfile.relative_to(src))
                found.setdefault(sym, info)
        if found:
            semistubs[dll_dir.name.lower()] = found
    # 3. prototypes
    protos = scan_headers(src / "include")
    # 4. install
    builtins = scan_install(args.install)
    # 5. api-sets
    apisets = parse_apisets(src / "dlls" / "apisetschema" / "apisetschema.spec")

    # compteurs
    n_exports = sum(1 for d in exports.values() for e in d.values() if e["t"] not in {"absent"})
    n_stubs = sum(1 for d in exports.values() for e in d.values() if e["t"] == "stub")
    n_absent = sum(1 for d in exports.values() for e in d.values() if e["t"] == "absent")
    n_semi = sum(len(v) for v in semistubs.values())
    kinds = Counter(info["kind"] for v in semistubs.values() for info in v.values())

    meta = {
        "wine_version": version,
        "source_dir": str(src),
        "source_tarball_sha256": args.tarball_sha256,
        "install_dir": str(args.install),
        "built_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "counts": {
            "spec_files": len(spec_files),
            "dlls_with_spec": len(exports),
            "exports": n_exports,
            "explicit_stubs": n_stubs,
            "commented_absent": n_absent,
            "semistub_functions": n_semi,
            "semistub_kinds": dict(kinds),
            "prototypes": len(protos),
            "apisets": len(apisets),
            "builtin_dlls_x86_64": len(builtins.get("x86_64", {})),
            "builtin_unix_x86_64": sum(1 for v in builtins.get("x86_64", {}).values() if v["unix"]),
        },
        "generator": "bdflab.knowledge.build_wine_db",
    }
    with gzip.open(out / "exports.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(exports, fh, separators=(",", ":"), sort_keys=True)
    (out / "semistubs.json").write_text(json.dumps(semistubs, indent=1, sort_keys=True, ensure_ascii=False))
    with gzip.open(out / "prototypes.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(protos, fh, separators=(",", ":"), sort_keys=True)
    (out / "builtins.json").write_text(json.dumps(builtins, indent=1, sort_keys=True))
    (out / "apisets.json").write_text(json.dumps(apisets, indent=1, sort_keys=True))
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
