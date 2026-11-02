"""Le Windows de l'utilisateur comme catalogue (idée : réutiliser une vraie copie de Windows, variante sûre).

Principe : une DLL Windows **native** peut remplacer la DLL Wine correspondante (override), si elle vient du
Windows **licencié de l'utilisateur** (jamais redistribuée par PolyRE) et si elle est **au-dessus du plancher**
— les DLL qui parlent au noyau NT par syscalls (ntdll, win32u, kernelbase, user32, gdi32…) doivent rester
celles de Wine, Linux n'ayant pas ces syscalls. Ce module inventorie un dossier ``System32`` fourni par
l'utilisateur en un manifeste d'empreintes, marque le plancher, et expose la règle de refus.

Limites honnêtes : une DLL native peut dépendre d'autres DLL natives ou de sémantiques noyau que Wine n'a
pas ; l'effet doit être **vérifié par oracle** comme tout autre correctif. Aucun Windows n'était disponible
sur ce banc : le mécanisme est implémenté et testé, pas exercé sur de vraies DLL Windows.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

# Plancher : DLL/EXE qui émettent des syscalls NT ou qui sont le noyau/chargeur eux-mêmes.
# Jamais remplaçables par une version Windows native sous Wine.
FLOOR_DLLS = {
    "ntdll", "win32u", "kernelbase", "kernel32", "user32", "gdi32", "ntoskrnl.exe", "hal", "winload",
    "ci", "wow64", "wow64win", "wow64cpu", "xtajit64", "advapi32", "sechost", "msvcrt", "ucrtbase",
    "combase", "rpcrt4", "ws2_32", "winmm", "imm32", "shcore", "windows.storage", "explorer.exe",
}
FLOOR_RATIONALE = ("émet des syscalls NT ou appartient au noyau/chargeur : Linux n'a pas ces syscalls, "
                   "la version Wine doit rester en place")


@dataclass
class NativeDllEntry:
    name: str
    sha256: str
    size: int
    version: str
    floor: bool
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def _version_of(path: Path) -> str:
    try:
        import pefile
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        if getattr(pe, "VS_FIXEDFILEINFO", None):
            f = pe.VS_FIXEDFILEINFO[0]
            return "%d.%d.%d.%d" % (f.FileVersionMS >> 16, f.FileVersionMS & 0xFFFF, f.FileVersionLS >> 16, f.FileVersionLS & 0xFFFF)
    except Exception:
        pass
    return ""


def is_floor(dll: str) -> bool:
    d = dll.lower()
    if d.endswith(".dll"):
        d = d[:-4]
    return d in FLOOR_DLLS or d.endswith(".sys") or d.endswith(".drv")


def inventory(system32: Path | str, out_manifest: Path | str | None = None, source_label: str = "windows-utilisateur") -> dict:
    """Inventorie un dossier System32 (du Windows de l'utilisateur) en manifeste d'empreintes."""
    root = Path(system32)
    entries: dict[str, dict] = {}
    for p in sorted(root.glob("*.dll")):
        try:
            data = p.read_bytes()
        except OSError:
            continue
        floor = is_floor(p.name)
        entries[p.name.lower()] = NativeDllEntry(
            name=p.name, sha256=hashlib.sha256(data).hexdigest(), size=len(data), version=_version_of(p),
            floor=floor, note=(FLOOR_RATIONALE if floor else "remplaçable en override natif, à vérifier par oracle")).to_dict()
    manifest = {
        "schema": "bdflab-user-windows-catalogue/0.1",
        "source": source_label,
        "redistribution": "INTERDITE — ces fichiers restent sur la machine de l'utilisateur ; seul ce manifeste d'empreintes circule",
        "floor_rule": FLOOR_RATIONALE,
        "entries": entries,
    }
    if out_manifest:
        Path(out_manifest).write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    return manifest


def propose_native_override(dll: str, manifest: dict) -> dict | None:
    """Contrat de classe A « DLL native depuis le Windows de l'utilisateur », ou None si refusé/absent."""
    key = dll.lower() if dll.lower().endswith(".dll") else dll.lower() + ".dll"
    if is_floor(dll):
        return {"refused": True, "dll": dll, "reason": f"plancher : {FLOOR_RATIONALE}"}
    e = manifest.get("entries", {}).get(key)
    if not e:
        return None
    return {"kind": "dll-native-user-windows", "dll": key[:-4], "sha256": e["sha256"], "version": e.get("version", ""),
            "mode": "native", "source": manifest.get("source", "windows-utilisateur"),
            "note": "override natif depuis la copie licenciée de l'utilisateur ; jamais redistribué ; à valider par oracle"}
