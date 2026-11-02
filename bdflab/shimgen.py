"""Génération et application d'un correctif de type « shim » (classe B).

Voie d'interception retenue pour v0.1 (HANDOFF §5, voie (a)+(b) combinées, documentée dans README) :
« proxy par redirection d'import ». Pour chaque DLL contenant une fonction non implémentée par Wine
et importée par la cible :

  1. on génère une DLL proxy qui ré-exporte TOUTES les fonctions importées de la DLL d'origine en
     les RENVOYANT (forwarders ``.def`` : ``Func = KERNEL32.Func``) vers la DLL Wine d'origine, SAUF
     les fonctions corrigées, qu'elle implémente réellement ;
  2. on patche une COPIE JETABLE de l'exécutable cible (jamais l'original) : dans le descripteur
     d'import, le nom de la DLL d'origine est remplacé, sur place, par celui du proxy (même longueur,
     terminé par NUL) à l'aide de ``pefile`` ;
  3. la DLL proxy est déposée à côté de la copie de l'exécutable, dans le préfixe Wine isolé.

Ainsi, même une DLL « always builtin » (kernel32, kernelbase, ntdll…) que WINEDLLOVERRIDES ne peut
pas remplacer globalement peut voir une seule de ses fonctions interceptée, sans toucher au moteur
Wine ni à l'exécutable d'origine.

Avantages : aucune modification de Wine ; l'original reste intact ; la correction est confinée au
préfixe jetable. Limites : imports par ordinal non redirigés (consignés) ; le nom du proxy doit tenir
dans la longueur du nom d'origine.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pefile

from .safety import (ERROR_CALL_NOT_IMPLEMENTED, E_NOTIMPL, S_OK, ERROR_NOT_SUPPORTED)

MINGW_CC = "x86_64-w64-mingw32-gcc"
MINGW_CC32 = "i686-w64-mingw32-gcc"


@dataclass
class ShimSpec:
    """Un shim : une fonction interceptée, sa stratégie et sa réponse."""
    dll: str                 # nom d'origine (ex. "kernel32")
    func: str
    strategy: str            # "A" ou "S"
    api_class: str
    ret_type: str            # type C du retour (ex. "BOOL", "HRESULT", "DWORD")
    returns: object          # valeur renvoyée (int) ou None
    last_error: object       # code SetLastError, ou None
    tainted: bool = False    # S => teinté/journalisé
    note: str = ""
    custom_c: str | None = None   # implémentation C COMPLÈTE proposée (fonderie) ; remplace le stub généré.
                                  # Doit définir le symbole « bdf_impl_<func> » (signature réelle).

    def to_dict(self) -> dict:
        return asdict(self)


RET_DEFS = {
    # type C -> (déclaration C, littéral succès, littéral échec-déclaré)
    "BOOL": ("int", "1", "0"),
    "WINBOOL": ("int", "1", "0"),
    "INT": ("int", "0", "0"),
    "int": ("int", "0", "0"),
    "DWORD": ("unsigned int", "0", "0"),
    "ULONG": ("unsigned int", "0", "0"),
    "UINT": ("unsigned int", "0", "0"),
    "LONG": ("int", "0", "0"),
    "LSTATUS": ("int", "0", "120"),            # ERROR_CALL_NOT_IMPLEMENTED
    "NTSTATUS": ("int", "0", "0xC0000002"),    # STATUS_NOT_IMPLEMENTED
    "HRESULT": ("int", "0", "0x80004001"),     # E_NOTIMPL
    "HANDLE": ("void*", "0", "0"),
    "HWND": ("void*", "0", "0"),
    "LPVOID": ("void*", "0", "0"),
    "void": ("void", "", ""),
    "VOID": ("void", "", ""),
    "": ("int", "0", "0"),
}


def default_response(api_class: str, ret_type: str, strategy: str) -> tuple[object, object]:
    """Valeur de retour + last_error par défaut selon la stratégie et le type."""
    rt = (ret_type or "").strip()
    decl, succ, fail = RET_DEFS.get(rt, RET_DEFS[""])
    if strategy == "A":
        # échec déclaré propre
        if rt in {"HRESULT"}:
            return (E_NOTIMPL, None)
        if rt in {"LSTATUS"}:
            return (ERROR_CALL_NOT_IMPLEMENTED, None)
        if rt in {"NTSTATUS"}:
            return (0xC0000002, None)
        if decl == "void*":
            return (0, ERROR_CALL_NOT_IMPLEMENTED)   # NULL + last error
        if decl == "void":
            return (None, None)
        # BOOL/DWORD/INT : 0 + last error
        return (0, ERROR_CALL_NOT_IMPLEMENTED)
    # strategy S : succès fabriqué
    if rt in {"HRESULT"}:
        return (S_OK, None)
    if rt in {"LSTATUS", "NTSTATUS"}:
        return (0, None)
    if decl == "void":
        return (None, None)
    if decl == "void*":
        return (0, None)   # un handle fabriqué NUL reste prudent ; S sur handle rarement utile
    return (1, None)       # BOOL TRUE / valeur non nulle


def c_type_for_decl(ret_type: str) -> str:
    return RET_DEFS.get((ret_type or "").strip(), RET_DEFS[""])[0]


@dataclass
class GeneratedShimDLL:
    original_dll: str
    proxy_dll_name: str       # avec extension, même longueur que l'original
    source_path: str
    def_path: str
    binary_path: str
    forwarded: int
    implemented: list[str]
    skipped_ordinals: list[str]
    build_log: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _proxy_name(original_dll: str, taken: set[str]) -> str:
    """Nom de proxy de MÊME longueur que l'original (contrainte de patch sur place)."""
    name = original_dll if original_dll.lower().endswith(".dll") else original_dll + ".dll"
    stem = name[:-4]
    L = len(stem)
    base = ("bz" + stem[2:]) if L >= 3 else ("b" * L)
    base = base[:L]
    cand = base + ".dll"
    i = 0
    while cand.lower() in taken:
        suffix = f"{i:x}"
        cand = (base[:L - len(suffix)] + suffix) + ".dll"
        i += 1
    return cand


def generate_shim_dll(original_dll: str, all_imported_funcs: list[str], shims: list[ShimSpec],
                      out_dir: Path, proxy_name: str | None = None, cc: str = MINGW_CC) -> GeneratedShimDLL:
    """Génère et compile une DLL proxy pour ``original_dll``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    orig = original_dll if original_dll.lower().endswith(".dll") else original_dll + ".dll"
    orig_stem_up = orig[:-4].upper()
    pname = proxy_name or _proxy_name(original_dll, set())
    assert len(pname) == len(orig), f"longueur proxy {pname} != {orig}"
    shim_by_name = {s.func: s for s in shims}

    skipped_ordinals = [f for f in all_imported_funcs if f.startswith("#")]
    named = [f for f in all_imported_funcs if not f.startswith("#")]
    # fonctions à implémenter réellement (même si pas toutes importées, on les garde)
    for s in shims:
        if s.func not in named:
            named.append(s.func)

    # --- source C des fonctions implémentées ---
    lines = [
        "/* DLL proxy générée par bdflab.shimgen — NE PAS ÉDITER À LA MAIN. */",
        "/* Forwarders vers " + orig_stem_up + " ; implémentations réelles pour les fonctions corrigées. */",
        "#define WIN32_LEAN_AND_MEAN",
        "#define _WIN32_WINNT 0x0601   /* API Windows 7+ visibles (structures dynamiques de fuseau, etc.) */",
        "#include <windows.h>",
        "#include <timezoneapi.h>",
        "#include <stdio.h>",
        "#include <string.h>",
        "",
        "static void bdf_log(const char *fn, const char *strat, const char *detail) {",
        "    const char *path = getenv(\"BDFLAB_SHIM_LOG\");",
        "    if (!path) return;",
        "    FILE *f = fopen(path, \"a\");",
        "    if (!f) return;",
        "    fprintf(f, \"shim|dll=%s|fn=%s|strategy=%s|%s\\n\", \"" + orig + "\", fn, strat, detail ? detail : \"\");",
        "    fclose(f);",
        "}",
        "",
    ]
    exports_impl: list[str] = []
    impl_symbol: dict[str, str] = {}
    for s in shims:
        decl = c_type_for_decl(s.ret_type)
        fn = s.func
        isym = "bdf_impl_" + fn
        impl_symbol[fn] = isym
        tainted = {"S": "S-tainted", "F": "F-fixture-recorded-on-windows"}.get(s.strategy, "A-declared-absence")
        if s.custom_c:
            # fonderie : implémentation proposée, émise telle quelle (elle sera jugée par l'oracle)
            lines.append(f"/* {fn}: implémentation PROPOSÉE (fonderie), stratégie {s.strategy}; {s.note} */")
            lines.append(s.custom_c.strip())
            lines.append("")
            exports_impl.append(fn)
            continue
        set_err = f"    SetLastError({int(s.last_error)});\n" if s.last_error not in (None,) else ""
        # Signature (void) : sur l'ABI Win64 (x86_64) l'appelant nettoie la pile et passe les
        # arguments en registres, donc une implémentation sans paramètre est sûre (les arguments
        # sont simplement ignorés, la valeur de retour part dans RAX). Sur x86 __stdcall il faudrait
        # décorer @N ; consigné comme limite v0.1.
        if decl == "void":
            body = f'    bdf_log("{fn}", "{s.strategy}", "void");\n{set_err}'
            sig = f"void {isym}(void) {{\n{body}}}"
        else:
            retval = s.returns if s.returns is not None else 0
            if isinstance(retval, int):
                retlit = hex(retval) if abs(retval) > 9 else str(retval)
            else:
                retlit = str(retval)
            cast = "(void*)" if decl == "void*" else ""
            body = (f'    bdf_log("{fn}", "{s.strategy}", "ret={retlit}");\n'
                    f"{set_err}"
                    f"    return {cast}{retlit};\n")
            sig = f"{decl} {isym}(void) {{\n{body}}}"
        lines.append(f"/* {fn}: classe API {s.api_class}, stratégie {s.strategy} ({tainted}); {s.note} */")
        lines.append(sig)
        lines.append("")
        exports_impl.append(fn)

    lines += [
        "BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r) { (void)h;(void)r;(void)reason; return TRUE; }",
        "",
    ]
    src = out_dir / (pname[:-4] + ".c")
    src.write_text("\n".join(lines))

    # --- .def : forwarders pour tout le reste, exports réels pour les shims ---
    deflines = [f"LIBRARY {pname[:-4]}", "EXPORTS"]
    impl_set = set(exports_impl)
    for f in sorted(set(named)):
        if f in impl_set:
            deflines.append(f"    {f} = {impl_symbol[f]}")    # alias vers l'implémentation locale
        else:
            deflines.append(f"    {f} = {orig_stem_up}.{f}")  # forwarder vers la DLL Wine d'origine
    dpath = out_dir / (pname[:-4] + ".def")
    dpath.write_text("\n".join(deflines) + "\n")

    # --- compilation ---
    binpath = out_dir / pname
    cmd = [cc, "-O1", "-shared", "-o", str(binpath), str(src), str(dpath),
           "-Wl,--no-insert-timestamp", "-static-libgcc", "-nostartfiles", "-Wl,--enable-stdcall-fixup"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    log = proc.stdout + proc.stderr
    if proc.returncode != 0 or not binpath.exists():
        # deuxième essai sans -nostartfiles (DllMain a besoin du CRT minimal pour getenv/fopen)
        cmd2 = [cc, "-O1", "-shared", "-o", str(binpath), str(src), str(dpath),
                "-Wl,--no-insert-timestamp", "-static-libgcc", "-Wl,--enable-stdcall-fixup"]
        proc = subprocess.run(cmd2, capture_output=True, text=True, timeout=180)
        log += "\n--- retry ---\n" + proc.stdout + proc.stderr
    if not binpath.exists():
        raise RuntimeError(f"échec de compilation du proxy {pname}:\n{log}")
    return GeneratedShimDLL(original_dll=orig, proxy_dll_name=pname, source_path=str(src), def_path=str(dpath),
                            binary_path=str(binpath), forwarded=len(set(named)) - len(impl_set),
                            implemented=sorted(impl_set), skipped_ordinals=skipped_ordinals, build_log=log.strip()[:4000])


@dataclass
class PatchResult:
    original_exe: str
    patched_exe: str
    renamed: list[dict]       # [{from, to}]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def patch_exe_imports(exe: Path, out_exe: Path, rename_map: dict[str, str]) -> PatchResult:
    """Copie l'exe et remplace, sur place, les noms de DLL importées selon ``rename_map``.

    ``rename_map`` : {"KERNEL32.dll": "bzRNEL32.dll", ...} — même longueur exigée.
    """
    out_exe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(exe, out_exe)
    pe = pefile.PE(str(out_exe))
    renamed: list[dict] = []
    notes: list[str] = []
    # normalisation insensible à la casse
    rmap = {k.lower(): v for k, v in rename_map.items()}
    entries = []
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        entries += list(pe.DIRECTORY_ENTRY_IMPORT)
    if hasattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT"):
        entries += list(pe.DIRECTORY_ENTRY_DELAY_IMPORT)
    for entry in entries:
        name = (entry.dll or b"").decode("ascii", "replace")
        tgt = rmap.get(name.lower())
        if not tgt:
            continue
        if len(tgt) != len(name):
            notes.append(f"longueur incompatible, DLL {name} non renommée (proxy {tgt})")
            continue
        name_rva = entry.struct.Name
        offset = pe.get_offset_from_rva(name_rva)
        pe.set_bytes_at_offset(offset, tgt.encode("ascii") + b"\x00")
        renamed.append({"from": name, "to": tgt})
    pe.write(str(out_exe))
    pe.close()
    return PatchResult(original_exe=str(exe), patched_exe=str(out_exe), renamed=renamed, notes=notes)
