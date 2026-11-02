"""Du « four d'extraction » au dossier autonome : importer une capture d'exécution en recette de capsule.

Idée (utilisateur) : lancer l'appli UNE fois dans la VM Windows de l'utilisateur, capturer **tout ce qu'elle
touche** (DLL chargées, clés de registre lues, fichiers, polices), mettre le nécessaire dans un dossier, puis
relancer **sans VM** : Wine fournit le socle, le dossier fournit le reste. Précédents Windows : ThinApp, Turbo,
App-V (capture → paquet portable). Ici la cible du paquet est un **préfixe Wine**.

Formats de capture acceptés :
  * **Process Monitor** (CSV exporté depuis la VM Windows : "Time of Day","Process Name","PID","Operation","Path","Result","Detail") ;
  * **journal Wine** (`+loaddll` et `+relay` : lignes « Loaded L"..." », appels Reg*) — permet de démontrer le
    pipeline sur Linux et d'affiner une capture Windows avec ce que Wine charge réellement.

Sortie : une **recette** (JSON) listant, par catégorie, ce qu'il faut extraire du Windows de l'utilisateur :
DLL natives candidates (hors plancher, avec le statut Wine de chacune pour prioriser), fichiers de l'appli,
clés de registre à exporter en `.reg`, polices. Les binaires Windows restent chez l'utilisateur ; seule la
recette (noms, empreintes attendues) peut circuler. Tout correctif issu de la recette reste à **vérifier par
oracle**. Limite structurelle : rien **sous** le plancher n'est extractible (ntdll, win32u, noyau, services).
"""
from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .userwindows import is_floor, FLOOR_RATIONALE

WIN_SYSDIRS = re.compile(r"^[A-Za-z]:\\(?:windows|winnt)\\(?:system32|syswow64|winsxs)\\", re.I)
WIN_FONTS = re.compile(r"^[A-Za-z]:\\(?:windows|winnt)\\fonts\\", re.I)
RE_LOADDLL = re.compile(r'Loaded L"(?P<path>[^"]+)" at (?P<addr>[0-9A-Fa-f]+): (?P<kind>native|builtin|PE builtin)')
RE_REGCALL = re.compile(r"Call (?:ADVAPI32|KERNELBASE|advapi32|kernelbase)\.Reg(?:Open|Query|Create)\w*\((?P<args>.*)\) ret=")
RE_WSTR = re.compile(r'L"([^"]*)"')


@dataclass
class Recipe:
    source_kind: str
    scenarios: list[str]
    app_root: str
    app_files: list[str]
    native_dll_candidates: list[dict]     # [{dll, path, wine_status, floor: False}]
    floor_refused: list[dict]             # DLL du plancher vues, jamais remplacées
    registry_keys: list[str]
    fonts: list[str]
    other_files: list[str]
    stats: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _norm_dll(path: str) -> str:
    name = path.replace("/", "\\").rsplit("\\", 1)[-1].lower()
    return name[:-4] if name.endswith(".dll") else name


def parse_procmon_csv(path: Path) -> dict:
    """Lit un export CSV de Process Monitor. Renvoie {dll_paths, reg_keys, file_paths}."""
    dll_paths: Counter = Counter(); reg_keys: Counter = Counter(); file_paths: Counter = Counter()
    with Path(path).open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            op = (row.get("Operation") or "").strip(); p = (row.get("Path") or "").strip()
            res = (row.get("Result") or "").strip().upper()
            if not p:
                continue
            if op == "Load Image" and p.lower().endswith((".dll", ".exe", ".drv", ".ocx")):
                dll_paths[p] += 1
            elif op.startswith("Reg") and res in ("SUCCESS", "BUFFER OVERFLOW", ""):
                reg_keys[p.rsplit("\\", 1)[0] if op in ("RegQueryValue", "RegSetValue") else p] += 1
            elif op in ("CreateFile", "ReadFile", "QueryOpen", "CreateFileMapping") and res in ("SUCCESS", ""):
                file_paths[p] += 1
    return {"dll_paths": dll_paths, "reg_keys": reg_keys, "file_paths": file_paths}


def parse_wine_log(path: Path) -> dict:
    """Lit un journal Wine (+loaddll, +relay). Renvoie {dll_paths, reg_keys, file_paths}."""
    dll_paths: Counter = Counter(); reg_keys: Counter = Counter(); file_paths: Counter = Counter()
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = RE_LOADDLL.search(line)
            if m:
                dll_paths[m.group("path").replace("\\\\", "\\")] += 1
                continue
            m = RE_REGCALL.search(line)
            if m:
                args = m.group("args")
                ws = RE_WSTR.findall(args)
                if ws:
                    # le premier argument est le handle racine (hex) : le traduire en ruche pour « reg export »
                    root = args.split(",", 1)[0].strip().lower()
                    hive = {"80000000": "HKCR", "80000001": "HKCU", "80000002": "HKLM",
                            "80000003": "HKU", "80000005": "HKCC"}.get(root)
                    key = ws[0].replace("\\\\", "\\")
                    reg_keys[(hive + "\\" + key) if hive and not re.match(r"^HK", key, re.I) else key] += 1
    return {"dll_paths": dll_paths, "reg_keys": reg_keys, "file_paths": file_paths}


def build_recipe(capture: dict, app_root: str, scenarios: list[str], source_kind: str, db=None) -> Recipe:
    app_root_n = app_root.replace("/", "\\").rstrip("\\").lower()
    app_files: set[str] = set(); natives: dict[str, dict] = {}; floor: dict[str, dict] = {}
    fonts: set[str] = set(); others: set[str] = set()
    for p in list(capture["dll_paths"]) + list(capture["file_paths"]):
        pl = p.replace("/", "\\").lower()
        if pl.startswith(app_root_n + "\\"):
            app_files.add(p); continue
        if WIN_FONTS.match(p):
            fonts.add(p); continue
        if pl.endswith((".dll", ".drv", ".ocx")) and WIN_SYSDIRS.match(p):
            d = _norm_dll(p)
            if is_floor(d):
                floor[d] = {"dll": d, "path": p, "reason": FLOOR_RATIONALE}
            else:
                status = "inconnu"
                if db is not None:
                    status = "fournie par Wine" if db.dll_known(d) else "ABSENTE de Wine"
                    if db.dll_known(d):
                        n_stub = len(db.stubs_of(d)); status += f" ({n_stub} stubs)" if n_stub else " (0 stub)"
                natives[d] = {"dll": d, "path": p, "wine_status": status, "floor": False}
            continue
        if not pl.endswith((".dll", ".exe")):
            others.add(p)
    reg = sorted({k for k in capture["reg_keys"] if k})
    # prioriser : DLL absentes de Wine ou à stubs d'abord
    cand = sorted(natives.values(), key=lambda x: (0 if "ABSENTE" in x["wine_status"] else (1 if "stubs)" in x["wine_status"] and "(0 stub)" not in x["wine_status"] else 2), x["dll"]))
    notes = ["Les DLL du plancher ne sont jamais remplacées : Wine les fournit (syscalls NT).",
             "Une seule capture ne couvre que les chemins exercés : capturer chaque scénario d'oracle.",
             "Les binaires Windows restent chez l'utilisateur ; la recette (noms/empreintes) seule peut circuler.",
             "Services Windows vivants (COM distants, WMI, Search) ne tiennent pas dans un dossier : partiel."]
    return Recipe(source_kind=source_kind, scenarios=scenarios, app_root=app_root, app_files=sorted(app_files),
                  native_dll_candidates=cand, floor_refused=sorted(floor.values(), key=lambda x: x["dll"]),
                  registry_keys=reg, fonts=sorted(fonts), other_files=sorted(others)[:200],
                  stats={"dll_loads": sum(capture["dll_paths"].values()), "distinct_dlls": len(capture["dll_paths"]),
                         "reg_keys": len(reg), "native_candidates": len(cand), "floor_seen": len(floor)}, notes=notes)


def to_extract_script(recipe: "Recipe", out_dir_name: str = "extrait-capsule") -> str:
    """Génère le script PowerShell à exécuter DANS la VM Windows de l'utilisateur : il copie dans un dossier
    exactement ce que la recette retient (DLL hors plancher, fichiers de l'appli, polices) et exporte les clés
    de registre en .reg. Rien du plancher n'est copié. Le dossier reste chez l'utilisateur."""
    L = []
    L.append("# Script d'extraction généré par polyre-bdf-lab (capture_import.to_extract_script).")
    L.append("# À exécuter DANS la VM Windows de l'utilisateur (PowerShell, droits lecture suffisants).")
    L.append("# Il copie ce que l'application a chargé — HORS plancher — dans un dossier local.")
    L.append("# Les fichiers copiés sont ceux de votre licence Windows : ils ne doivent PAS être redistribués.")
    L.append(f"$out = Join-Path (Get-Location) '{out_dir_name}'")
    for sub in ("dlls", "app", "fonts", "registry"):
        L.append(f"New-Item -ItemType Directory -Force -Path (Join-Path $out '{sub}') | Out-Null")
    L.append("")
    L.append("# --- DLL natives hors plancher (priorisées par le statut Wine) ---")
    for c in recipe.native_dll_candidates:
        src = c["path"].replace("'", "''")
        L.append(f"Copy-Item -LiteralPath '{src}' -Destination (Join-Path $out 'dlls') -ErrorAction SilentlyContinue  # {c['wine_status']}")
    L.append("")
    L.append("# --- plancher : volontairement NON copié (Wine le fournit) ---")
    for f in recipe.floor_refused:
        L.append(f"# [plancher] {f['dll']}")
    L.append("")
    L.append("# --- fichiers de l'application ---")
    for f in recipe.app_files:
        src = f.replace("'", "''")
        L.append(f"Copy-Item -LiteralPath '{src}' -Destination (Join-Path $out 'app') -ErrorAction SilentlyContinue")
    L.append("")
    L.append("# --- polices ---")
    for f in recipe.fonts:
        src = f.replace("'", "''")
        L.append(f"Copy-Item -LiteralPath '{src}' -Destination (Join-Path $out 'fonts') -ErrorAction SilentlyContinue")
    L.append("")
    L.append("# --- registre : export des clés lues (format .reg, importable dans le préfixe Wine) ---")
    for i, k in enumerate(recipe.registry_keys):
        if not re.match(r"^(HKLM|HKCU|HKCR|HKU|HKCC)\\", k, re.I):
            continue
        safe = re.sub(r"[^A-Za-z0-9]+", "_", k)[:80]
        L.append(f"reg export '{k}' (Join-Path $out 'registry\\{i:03d}_{safe}.reg') /y 2>$null")
    L.append("")
    L.append("# --- manifeste d'empreintes (seul élément destiné à circuler) ---")
    L.append("Get-ChildItem -Recurse -File $out | Get-FileHash -Algorithm SHA256 | Select-Object Hash, Path | Export-Csv (Join-Path $out 'MANIFEST-sha256.csv') -NoTypeInformation")
    L.append("Write-Host \"Extraction terminée dans $out — copiez le dossier sur la machine Linux (il reste privé).\"")
    return "\n".join(L) + "\n"
