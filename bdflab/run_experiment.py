#!/usr/bin/env python3
"""Pilote de l'expérience phase 0 de polyre-bdf-lab.

Usage :
  python3 -m bdflab.run_experiment --exe testapps/bdfedit/bin/bdfedit.exe \
      --data data/wine-11.0 --work "$BDFLAB_WORK" \
      --out results --synthetic [--scenarios edit-save-reopen,stats-degrade,...] [--runs 2]

Produit dans ``results/<horodatage>/`` : ``results.json``, les journaux/traces par exécution, les
fichiers produits (preuves), et une capsule TOML dans ``capsules/``.
"""
from __future__ import annotations

import os

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import time
from pathlib import Path

from .wine_db import WineDB
from .wine_runner import wine_info, preflight, PrefixManager
from . import pe_surface, fixgen, experiment
from .experiment import SCENARIOS, run_scenario, summarize, RunRecord, ExperimentResult
from .capsule import build_capsule


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exe", required=True, type=Path)
    ap.add_argument("--data", type=Path, default=Path("data/wine-11.0"))
    ap.add_argument("--work", type=Path, default=Path(os.environ.get("BDFLAB_WORK", Path(__file__).resolve().parent.parent / "_scratch" / "bdflab-work")),
                    help="espace de travail jetable (défaut : $BDFLAB_WORK ou <dépôt>/_scratch/bdflab-work)")
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--catalogue", type=Path, default=Path("catalogue"))
    ap.add_argument("--manual-dll", type=Path, default=Path("manual-fix/bzmank32.dll"))
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--scenarios", default="", help="liste séparée par des virgules ; vide = tous")
    ap.add_argument("--configs", default="A,B,C")
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parent.parent
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_dir = (args.out / stamp).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    wi = wine_info()
    pf = preflight(args.work)
    print(f"[preflight] ok={pf.ok} disk={pf.disk_free_gb}Go mem={pf.mem_available_gb}Go smart={pf.smart} wineprocs={pf.wine_processes}")
    if not pf.ok:
        print("[preflight] conditions non réunies :", pf.messages)
        return 3

    db = WineDB(args.data)
    exe = args.exe
    print(f"[analyse] {exe} sous Wine {wi.version}")
    surface = pe_surface.analyze(exe, db)
    (results_dir / "pe_surface.json").write_text(json.dumps(surface.to_dict(), indent=1, ensure_ascii=False))
    print(f"[analyse] imports={surface.summary['imports_total']} problématiques={surface.summary['problematic']}")

    # catalogue du labo : nom.dll -> sha256
    catalogue: dict[str, str] = {}
    cat_dir = args.catalogue
    if cat_dir.is_dir():
        for p in sorted(cat_dir.glob("*.dll")):
            catalogue[p.stem] = sha256_file(p)
    # le PDF de test est aussi dans testapps (dépendance synthétique redistribuable par nous)
    pdf_src = exe.parent / "bdfpdf.dll"
    if pdf_src.exists():
        catalogue.setdefault("bdfpdf", sha256_file(pdf_src))

    # --- diagnostic + génération du correctif (config B), chronométré ---
    problems = fixgen.diagnose(surface, db, catalogue)
    (results_dir / "diagnosis.json").write_text(json.dumps([p.to_dict() for p in problems], indent=1, ensure_ascii=False))
    t0 = time.time()
    plan = fixgen.plan_fixes(surface, problems, db, catalogue, synthetic=args.synthetic)
    fix_out = results_dir / "fix-B"
    built = fixgen.build_fix(plan, exe, fix_out, surface, catalogue_dir=(cat_dir if cat_dir.is_dir() else exe.parent))
    gen_time_b = round(time.time() - t0, 3)
    (results_dir / "fixplan.json").write_text(json.dumps(plan.to_dict(), indent=1, ensure_ascii=False, default=str))
    (results_dir / "fix-B" / "built.json").write_text(json.dumps(built.to_dict(), indent=1, ensure_ascii=False))
    print(f"[config B] correctif généré en {gen_time_b}s : {len(plan.shims)} shim(s), {len(plan.declarative)} contrat(s) A")
    for a in built.actions:
        print("          -", a)

    # --- config C : correctif manuel de référence (construit si besoin), chronométré (build seul) ---
    manual_build_c = 0.0
    manual_dll = args.manual_dll
    if not manual_dll.exists() and (manual_dll.parent / "build_manual.sh").exists():
        t0 = time.time()
        subprocess.run(["bash", str(manual_dll.parent / "build_manual.sh")], check=True, capture_output=True)
        manual_build_c = round(time.time() - t0, 3)
    # copie de l'exe redirigée vers la DLL manuelle
    cfgC_dir = results_dir / "fix-C"
    cfgC_dir.mkdir(exist_ok=True)
    patchedC = None
    if manual_dll.exists():
        from .shimgen import patch_exe_imports
        # nom d'origine exact
        orig_exact = next((i.dll for i in surface.imports if i.dll.lower().startswith("kernel32")), "KERNEL32.dll")
        pr = patch_exe_imports(exe, cfgC_dir / exe.name, {orig_exact: manual_dll.name})
        patchedC = pr.patched_exe
        import shutil
        shutil.copy2(manual_dll, cfgC_dir / manual_dll.name)
        (cfgC_dir / "patch.json").write_text(json.dumps(pr.to_dict(), indent=1, ensure_ascii=False))

    # --- bundles par configuration ---
    bundles = {
        "A": {"exe": exe, "dlls": [], "pdf_dll": None},  # standard : rien ajouté (gap classe A visible)
        "B": {"exe": Path(built.patched_exe), "dlls": [fix_out / g["proxy_dll_name"] for g in built.generated_dlls],
              "pdf_dll": pdf_src if pdf_src.exists() else None},
        "C": {"exe": Path(patchedC) if patchedC else exe,
              "dlls": [cfgC_dir / manual_dll.name] if manual_dll.exists() else [],
              "pdf_dll": pdf_src if pdf_src.exists() else None},
    }

    want_scen = [s.strip() for s in args.scenarios.split(",") if s.strip()] or [s["name"] for s in SCENARIOS]
    scen_list = [s for s in SCENARIOS if s["name"] in want_scen]
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]

    pm = PrefixManager(args.work, wi)
    print(f"[gabarit] préparation du préfixe modèle Wine {wi.version}…")
    pm.ensure_template()

    records: list[RunRecord] = []
    for sc in scen_list:
        for c in configs:
            for ridx in range(1, args.runs + 1):
                diagnostic = (c == "A")  # trace relay complète seulement pour la référence (preuve)
                print(f"[run] config {c} · {sc['name']} · essai {ridx}/{args.runs} (debug={'relay' if diagnostic else 'light'})")
                rec = run_scenario(pm, args.work, c, bundles[c], sc, ridx, results_dir, diagnostic)
                status = "PASS" if rec.passed else "FAIL"
                fs = " [FAUX SUCCÈS]" if rec.false_success else ""
                print(f"      -> {status}{fs} exit={rec.exit_code} wall={rec.wall_s}s cpu={rec.cpu_s}s rss={rec.peak_rss_kb//1024}Mo events={rec.app_events}")
                records.append(rec)

    comparison = summarize(records, configs, [s["name"] for s in scen_list])

    # --- capsule depuis la config B (si B jouée) ---
    capsule_path = ""
    if "B" in configs:
        res_by_scen = {}
        for sc in scen_list:
            recs = [r for r in records if r.config == "B" and r.scenario == sc["name"]]
            if recs:
                allpass = all(r.passed for r in recs)
                anyfs = any(r.false_success for r in recs)
                res_by_scen[sc["name"]] = "pass" if (allpass and not anyfs) else ("false-success" if anyfs else "fail")
        # preuves par fonction : lignes de trace de la config A (diagnostic)
        evidence = {}
        for r in records:
            if r.config == "A":
                for sct in r.trace_summary.get("stub_calls", []):
                    evidence.setdefault(sct["func"], []).append(
                        f"trace:{r.config}/{r.scenario}/r{r.run_idx}:{sct['module']}.{sct['func']}@{sct['addr']}")
        b_all_pass = all(v == "pass" for v in res_by_scen.values())
        status = "experimental"  # une victoire synthétique ne vaut pas validation sur logiciel réel
        cap = build_capsule(
            identity=pe_surface.identity_of(surface), wine_version=wi.version, polyre_range=">=0.4, <0.5",
            contracts=[{"kind": c.kind, "dll": c.dll, "source": c.catalogue_source, "sha256": c.sha256, "mode": c.mode}
                       for c in plan.declarative],
            shims=[{"dll": s.dll, "func": s.func, "strategy": s.strategy, "api_class": s.api_class,
                    "returns": s.returns, "last_error": s.last_error, "tainted": s.tainted, "note": s.note}
                   for s in plan.shims],
            scenarios=[s["name"] for s in scen_list], results=res_by_scen, runs=args.runs, machines=1,
            status=status, synthetic=args.synthetic, evidence_by_func=evidence)
        caps_dir = repo / "capsules"
        caps_dir.mkdir(exist_ok=True)
        ident = pe_surface.identity_of(surface)
        capsule_path = str(caps_dir / f"{ident['product'].split()[0].lower()}-{surface.sha256[:12]}.capsule.toml")
        cap.dump(Path(capsule_path))
        # lint
        from .capsule import lint_capsule, load_capsule
        lr = lint_capsule(load_capsule(capsule_path))
        (results_dir / "capsule_lint.json").write_text(json.dumps({"ok": lr.ok, "errors": lr.errors, "warnings": lr.warnings}, indent=1, ensure_ascii=False))
        print(f"[capsule] {capsule_path} — lint ok={lr.ok} erreurs={len(lr.errors)} avertissements={len(lr.warnings)}")

    exp = ExperimentResult(
        wine={"version": wi.version, "package": wi.package, "bin": wi.bin_dir},
        started=stamp, scenarios=[s["name"] for s in scen_list], configs=configs,
        records=[r.to_dict() for r in records], gen_time_b_s=gen_time_b, gen_actions_b=built.actions,
        manual_build_c_s=manual_build_c, comparison=comparison, capsule_path=capsule_path)
    (results_dir / "results.json").write_text(json.dumps(exp.to_dict(), indent=1, ensure_ascii=False, default=str))
    # lien 'latest'
    latest = args.out / "latest"
    try:
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(results_dir.name)
    except OSError:
        pass

    print("\n==== RÉSUMÉ ====")
    for c in configs:
        t = comparison["table"][c]
        print(f"config {c}: {t['scenario_passes']}/{t['runs']} exécutions réussies · faux succès={t['false_success']} · "
              f"reproductible={t['reproducible']} · cpu~{t['cpu_s_mean']}s · rss~{t['peak_rss_mb_mean']}Mo")
    print("régressions:", comparison["regressions"] or "aucune")
    print(f"temps de génération config B: {gen_time_b}s | build config C: {manual_build_c}s")
    print(f"résultats: {results_dir}/results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
