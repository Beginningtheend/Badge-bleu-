#!/usr/bin/env python3
"""Capture (export CSV Process Monitor depuis la VM, ou journal Wine) -> recette de capsule + extract.ps1.

Exemple (depuis la racine du dépôt) :
  python3 tools/capture_to_recipe.py --procmon _captures/monapp/s1.csv --procmon _captures/monapp/s2.csv \
      --app-root "C:/Program Files/MonApp" --scenario ouvrir-modifier-enregistrer --scenario export \
      --out _captures/monapp
Sorties : <out>/recipe.json et <out>/extract.ps1 (à exécuter DANS la VM). `_captures/` est ignoré par git :
une capture contient des chemins et noms d'utilisateur Windows ; la recette aussi, ne la versionne pas telle quelle.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bdflab.capture_import import parse_procmon_csv, parse_wine_log, build_recipe, to_extract_script
from bdflab.wine_db import WineDB


def merge(captures: list[dict]) -> dict:
    out: dict = {}
    for c in captures:
        for k, v in c.items():
            if isinstance(v, list):
                out.setdefault(k, [])
                out[k] += [x for x in v if x not in out[k]]
            elif isinstance(v, dict):
                out.setdefault(k, {}).update(v)
            else:
                out.setdefault(k, v)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--procmon", action="append", default=[], type=Path, help="export CSV Process Monitor (répétable)")
    ap.add_argument("--wine-log", action="append", default=[], type=Path, help="journal Wine +loaddll/+relay (répétable)")
    ap.add_argument("--app-root", required=True, help="dossier d'installation de l'application dans la VM (ex. C:/Program Files/App)")
    ap.add_argument("--scenario", action="append", default=[], help="nom de scénario joué (répétable)")
    ap.add_argument("--data", type=Path, default=Path("data/wine-11.0"), help="base de connaissances Wine (priorisation)")
    ap.add_argument("--out", type=Path, required=True, help="dossier de sortie (hors dépôt : _captures/<app>)")
    a = ap.parse_args(argv)
    if not a.procmon and not a.wine_log:
        ap.error("au moins un --procmon ou --wine-log")
    caps = [parse_procmon_csv(p) for p in a.procmon] + [parse_wine_log(p) for p in a.wine_log]
    kind = "procmon-csv" if a.procmon and not a.wine_log else ("wine-log" if a.wine_log and not a.procmon else "procmon-csv+wine-log")
    db = WineDB(a.data) if (a.data / "meta.json").exists() else None
    if db is None:
        print(f"avertissement : base {a.data} absente, priorisation par statut Wine inopérante", file=sys.stderr)
    recipe = build_recipe(merge(caps), app_root=a.app_root, scenarios=a.scenario or ["(non nommé)"], source_kind=kind, db=db)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "recipe.json").write_text(json.dumps(recipe.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    (a.out / "extract.ps1").write_text(to_extract_script(recipe), encoding="utf-8")
    print(f"recette : {a.out/'recipe.json'} ; script VM : {a.out/'extract.ps1'} ; "
          f"DLL natives candidates : {len(recipe.native_dll_candidates)}, plancher refusé : {len(recipe.floor_refused)}, "
          f"clés de registre : {len(recipe.registry_keys)}, fichiers appli : {len(recipe.app_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
