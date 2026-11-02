"""Analyse statique d'un exécutable PE : identité, imports, croisement avec la base Wine.

Outil éprouvé utilisé : ``pefile`` (imports, delay-imports, VERSIONINFO, imphash). Le croisement
avec les ``.spec`` de Wine vient de :mod:`bdflab.wine_db`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pefile

from .wine_db import WineDB, Resolution, norm_dll

MACHINES = {0x14C: "i386", 0x8664: "x86_64", 0xAA64: "arm64", 0x1C0: "arm"}
SUBSYSTEMS = {2: "gui", 3: "console", 9: "ce-gui"}

DLL_STRING_RE = re.compile(rb"[A-Za-z0-9_\-.]{2,60}\.(?:dll|DLL|Dll)")
DLL_WSTRING_RE = re.compile(rb"(?:[A-Za-z0-9_\-.]\x00){2,60}\.\x00(?:[dD]\x00[lL]\x00[lL]\x00)")


@dataclass
class ImportFinding:
    dll: str            # nom tel qu'importé (ex. KERNEL32.dll)
    func: str           # nom de fonction, ou "#<ordinal>"
    delay: bool
    resolution: dict    # Resolution.to_dict()


@dataclass
class PESurface:
    path: str
    sha256: str
    size: int
    imphash: str
    machine: str
    subsystem: str
    is_dll: bool
    timestamp: int
    linker: str
    authenticode: bool
    version_info: dict
    imports: list[ImportFinding]
    dynamic_dll_candidates: list[str]
    wine_version: str
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def problematic(self) -> list[ImportFinding]:
        return [i for i in self.imports if i.resolution["status"] != "implemented"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _version_info(pe: pefile.PE) -> dict:
    info: dict = {}
    try:
        if hasattr(pe, "VS_VERSIONINFO") and hasattr(pe, "FileInfo"):
            for fi_list in pe.FileInfo:
                for fi in fi_list:
                    if fi.Key == b"StringFileInfo":
                        for st in fi.StringTable:
                            for k, v in st.entries.items():
                                info[k.decode("utf-8", "replace")] = v.decode("utf-8", "replace")
        if hasattr(pe, "VS_FIXEDFILEINFO") and pe.VS_FIXEDFILEINFO:
            ffi = pe.VS_FIXEDFILEINFO[0]
            info["_FixedProductVersion"] = "%d.%d.%d.%d" % (
                ffi.ProductVersionMS >> 16, ffi.ProductVersionMS & 0xFFFF,
                ffi.ProductVersionLS >> 16, ffi.ProductVersionLS & 0xFFFF)
            info["_FixedFileVersion"] = "%d.%d.%d.%d" % (
                ffi.FileVersionMS >> 16, ffi.FileVersionMS & 0xFFFF,
                ffi.FileVersionLS >> 16, ffi.FileVersionLS & 0xFFFF)
    except Exception as exc:  # pragma: no cover - pefile est tolérant mais pas infaillible
        info["_error"] = repr(exc)
    return info


def _dynamic_dll_candidates(data: bytes, static: set[str]) -> list[str]:
    found: set[str] = set()
    for m in DLL_STRING_RE.finditer(data):
        found.add(m.group(0).decode("ascii", "replace").lower())
    for m in DLL_WSTRING_RE.finditer(data):
        try:
            found.add(m.group(0).decode("utf-16-le", "replace").lower())
        except Exception:
            pass
    return sorted(f for f in found if norm_dll(f) not in static and not f.startswith("."))


def analyze(path: Path | str, db: WineDB, arch_hint: str | None = None) -> PESurface:
    path = Path(path)
    data = path.read_bytes()
    pe = pefile.PE(data=data, fast_load=True)
    pe.parse_data_directories(directories=[
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"],
        pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"],
    ])
    machine = MACHINES.get(pe.FILE_HEADER.Machine, hex(pe.FILE_HEADER.Machine))
    arch = arch_hint or machine
    subsystem = SUBSYSTEMS.get(pe.OPTIONAL_HEADER.Subsystem, str(pe.OPTIONAL_HEADER.Subsystem))
    sec_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_SECURITY"]]
    imports: list[ImportFinding] = []
    static_dlls: set[str] = set()

    def add_entries(entries, delay: bool) -> None:
        for entry in entries:
            dll = entry.dll.decode("utf-8", "replace") if entry.dll else "?"
            static_dlls.add(norm_dll(dll))
            for imp in entry.imports:
                if imp.name:
                    func = imp.name.decode("utf-8", "replace")
                else:
                    func = f"#{imp.ordinal}"
                res = db.resolve(dll, func, arch) if not func.startswith("#") else Resolution(
                    dll=norm_dll(dll), func=func, status="implemented" if db.dll_known(dll, arch) else "dll-missing",
                    notes=["import par ordinal : non résolu statiquement"])
                imports.append(ImportFinding(dll=dll, func=func, delay=delay, resolution=res.to_dict()))

    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        add_entries(pe.DIRECTORY_ENTRY_IMPORT, delay=False)
    if hasattr(pe, "DIRECTORY_ENTRY_DELAY_IMPORT"):
        add_entries(pe.DIRECTORY_ENTRY_DELAY_IMPORT, delay=True)

    counts: dict[str, int] = {}
    for i in imports:
        counts[i.resolution["status"]] = counts.get(i.resolution["status"], 0) + 1
    try:
        imphash = pe.get_imphash()
    except Exception:
        imphash = ""
    surface = PESurface(
        path=str(path),
        sha256=hashlib.sha256(data).hexdigest(),
        size=len(data),
        imphash=imphash,
        machine=machine,
        subsystem=subsystem,
        is_dll=bool(pe.FILE_HEADER.Characteristics & 0x2000),
        timestamp=int(pe.FILE_HEADER.TimeDateStamp),
        linker=f"{pe.OPTIONAL_HEADER.MajorLinkerVersion}.{pe.OPTIONAL_HEADER.MinorLinkerVersion}",
        authenticode=bool(sec_dir.Size),
        version_info=_version_info(pe),
        imports=imports,
        dynamic_dll_candidates=_dynamic_dll_candidates(data, static_dlls),
        wine_version=db.wine_version,
        summary={
            "imports_total": len(imports),
            "import_dlls": sorted(static_dlls),
            "by_status": counts,
            "problematic": [f"{i.dll}!{i.func} [{i.resolution['status']}]" for i in imports
                            if i.resolution["status"] != "implemented"],
        },
    )
    return surface


def identity_of(surface: PESurface) -> dict:
    vi = surface.version_info
    return {
        "sha256": surface.sha256,
        "imphash": surface.imphash,
        "product": vi.get("ProductName", "") or vi.get("InternalName", "") or Path(surface.path).name,
        "version": vi.get("ProductVersion", "") or vi.get("_FixedProductVersion", ""),
        "publisher": vi.get("CompanyName", ""),
        "file": Path(surface.path).name,
        "machine": surface.machine,
        "authenticode": surface.authenticode,
    }
