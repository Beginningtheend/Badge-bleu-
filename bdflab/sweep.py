#!/usr/bin/env python3
"""Balayage statique d'un corpus d'exécutables PE : portée de l'analyseur, SANS exécution.

Honnêteté des comptages (essentiel) :
  * une DLL « manquante » présente ailleurs dans le corpus est une DLL PRIVÉE de l'application
    (livrée avec elle, présente à l'exécution) : ce n'est PAS une lacune de compatibilité, on l'exclut ;
  * un « api-set » (api-ms-win-*, ext-ms-win-*) qui se résout vers une DLL Wine n'est pas manquant ;
  * on sépare les cas DURS (l'appel échouerait : @ stub, export absent, DLL de runtime réellement
    absente) des SEMI-STUBS (implémentation partielle de Wine, qui fonctionne souvent) ;
  * un import problématique en analyse statique n'est pas forcément atteint à l'exécution : le balayage
    mesure la PORTÉE de l'analyseur, pas un taux de panne.

Usage : python3 -m bdflab.sweep --dir _corpus/extracted --data data/wine-11.0 --out results/sweep.json
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .wine_db import WineDB, norm_dll
from . import pe_surface
from .classify import classify_problem, RUNTIME_HINTS


def corpus_dll_set(root: Path) -> set[str]:
    out: set[str] = set()
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".dll", ".pyd", ".ocx", ".cpl", ".drv"}:
            out.add(norm_dll(p.name))
    return out


def analyze_one(path: Path, db: WineDB, corpus_dlls: set[str]) -> dict:
    try:
        s = pe_surface.analyze(path, db)
    except Exception as exc:
        return {"file": str(path), "name": path.name, "error": f"{type(exc).__name__}: {exc}"}
    buckets = {"hard_B": [], "hard_D": [], "hard_C": [], "semi_stub": [], "missing_runtime_A": [],
               "app_private": [], "other_missing": []}
    for imp in s.imports:
        res = imp.resolution
        st = res["status"]
        if st == "implemented":
            continue
        dll = res["dll"]
        label = f"{dll}.{imp.func}"
        if st == "dll-missing":
            if dll in corpus_dlls:
                buckets["app_private"].append(label)
                continue
            hint = next((v for k, v in RUNTIME_HINTS.items() if dll.startswith(k)), None)
            if hint or dll in {"msvcp140", "vcruntime140", "mfc140", "mfc140u", "mscoree", "gdiplus"}:
                buckets["missing_runtime_A"].append(label)
            else:
                buckets["other_missing"].append(label)
            continue
        if st == "semi-stub":
            buckets["semi_stub"].append(label)
            continue
        if st in {"stub", "export-absent", "forward-broken"}:
            p = classify_problem(dll, imp.func, st, res.get("prototype"), [], resolution_notes=res.get("notes"))
            if p.contract_class == "D":
                buckets["hard_D"].append(label)
            elif p.contract_class == "C":
                buckets["hard_C"].append(label)
            else:
                buckets["hard_B"].append(label)
    return {
        "file": str(path), "name": path.name, "machine": s.machine, "subsystem": s.subsystem,
        "sha256": s.sha256[:16], "imphash": s.imphash, "authenticode": s.authenticode,
        "imports_total": s.summary["imports_total"],
        "counts": {k: len(v) for k, v in buckets.items()},
        "hard_B_funcs": sorted(set(buckets["hard_B"])),
        "hard_D_funcs": sorted(set(buckets["hard_D"])),
        "missing_runtime_A": sorted(set(buckets["missing_runtime_A"])),
        "semi_stub_sample": sorted(set(buckets["semi_stub"]))[:20],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--data", type=Path, default=Path("data/wine-11.0"))
    ap.add_argument("--out", type=Path, default=Path("results/sweep.json"))
    ap.add_argument("--exts", default=".exe,.dll,.pyd,.ocx,.cpl")
    args = ap.parse_args(argv)
    db = WineDB(args.data)
    exts = {e if e.startswith(".") else "." + e for e in args.exts.split(",")}
    corpus_dlls = corpus_dll_set(args.dir)
    files = sorted(p for p in args.dir.rglob("*") if p.is_file() and p.suffix.lower() in exts)
    per_file = []
    errors = 0
    agg = Counter()
    hardB_funcs = Counter()
    hardD_funcs = Counter()
    runtimeA = Counter()
    semi_funcs = Counter()
    apps_hardB = set()
    apps_runtimeA = set()
    for p in files:
        r = analyze_one(p, db, corpus_dlls)
        per_file.append(r)
        if "error" in r:
            errors += 1
            continue
        for k, v in r["counts"].items():
            agg[k] += v
        for f in r["hard_B_funcs"]:
            hardB_funcs[f] += 1
        for f in r["hard_D_funcs"]:
            hardD_funcs[f] += 1
        for f in r["missing_runtime_A"]:
            runtimeA[f] += 1
        for f in r["semi_stub_sample"]:
            semi_funcs[f] += 1
        if r["counts"]["hard_B"]:
            apps_hardB.add(r["name"])
        if r["counts"]["missing_runtime_A"]:
            apps_runtimeA.add(r["name"])
    summary = {
        "corpus_dir": str(args.dir), "pe_files": len(files), "analyzed": len(files) - errors, "errors": errors,
        "distinct_app_private_dlls_excluded": sorted({f.split(".")[0] for r in per_file if "counts" in r for f in r.get("hard_B_funcs", []) })[:0] or "voir note",
        "import_sites": {
            "hard_B_shimmable": agg["hard_B"],
            "hard_D_refused_security": agg["hard_D"],
            "hard_C_escalate": agg["hard_C"],
            "semi_stub_partial": agg["semi_stub"],
            "missing_runtime_A": agg["missing_runtime_A"],
            "app_private_excluded": agg["app_private"],
            "other_missing_noncatalogue": agg["other_missing"],
        },
        "apps_with_hard_B": {"count": len(apps_hardB), "names": sorted(apps_hardB)},
        "apps_with_missing_runtime_A": {"count": len(apps_runtimeA), "names": sorted(apps_runtimeA)},
        "top_hard_B_functions": hardB_funcs.most_common(25),
        "top_security_D_functions": hardD_funcs.most_common(15),
        "top_missing_runtime_A": runtimeA.most_common(15),
        "top_semi_stub_functions": semi_funcs.most_common(15),
        "machines": dict(Counter(r.get("machine") for r in per_file if "machine" in r)),
    }
    out = {"summary": summary, "per_file": per_file}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    import pprint
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
