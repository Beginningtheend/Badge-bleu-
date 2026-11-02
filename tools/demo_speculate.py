#!/usr/bin/env python3
"""Démo : découverte automatique de la réponse d'un stub par recherche + oracle (bdflab.speculate).

Cible : shcore.IsAppCompatModeEnabled (vrai stub Wine 11.0), utilisé par le scénario « capability » du
programme de test : l'enregistrement n'a lieu que si la capacité répond « disponible » (TRUE).
Le labo essaie les réponses sûres (A: FALSE+err ; S: TRUE) et retient celle dont l'EFFET est vérifié.

Usage : python3 tools/demo_speculate.py
"""
from __future__ import annotations
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bdflab.wine_db import WineDB
from bdflab import pe_surface, oracles
from bdflab.fixgen import FixPlan, build_fix
from bdflab.shimgen import ShimSpec
from bdflab.wine_runner import wine_info, PrefixManager, RunLock, run_wine
from bdflab.trace_parser import parse_app_stdout
from bdflab.speculate import search_answer, candidate_answers

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "testapps/bdfedit/bin/bdfedit.exe"
WORK = Path("/home/user/_scratch/bdflab-work")
MARKER = "capability-marker-7731"
DISK = "C:/bdf"


def main() -> int:
    db = WineDB(REPO / "data/wine-11.0")
    wi = wine_info()
    s = pe_surface.analyze(EXE, db)
    pm = PrefixManager(WORK, wi)
    pm.ensure_template()

    # réponses A par défaut pour les stubs kernel32 (pour que le chemin edit interne ne plante pas)
    k32 = [
        ShimSpec("kernel32", "SystemTimeToTzSpecificLocalTimeEx", "A", "output-buffer", "BOOL", 0, 120, note="repli"),
        ShimSpec("kernel32", "Heap32First", "A", "output-buffer", "BOOL", 0, 120),
        ShimSpec("kernel32", "Heap32Next", "A", "output-buffer", "BOOL", 0, 120),
    ]

    trial_dir = Path("/home/user/_scratch/speculate"); shutil.rmtree(trial_dir, ignore_errors=True)
    trial_dir.mkdir(parents=True)
    run_counter = {"n": 0}

    def evaluate(cand):
        run_counter["n"] += 1
        tag = f"cand{run_counter['n']}-{cand.strategy}"
        d = trial_dir / tag
        shcore = ShimSpec("shcore", "IsAppCompatModeEnabled", cand.strategy, "state-query", "BOOL",
                          cand.returns, cand.last_error, tainted=(cand.strategy == "S"))
        plan = FixPlan(identity={}, problems=[], declarative=[], shims=k32 + [shcore], rejected=[], notes=[])
        bf = build_fix(plan, EXE, d / "fix", s)
        # préfixe propre, on stage l'exe corrigé + les DLL de compatibilité
        px = pm.fresh_prefix(tag)
        bdf = px / "drive_c" / "bdf"; bdf.mkdir(parents=True)
        shutil.copy2(bf.patched_exe, bdf / "bdfedit.exe")
        for g in bf.generated_dlls:
            shutil.copy2(g["binary_path"], bdf / g["proxy_dll_name"])
        (bdf / "doc.txt").write_text("contenu de reference\n", encoding="utf-8")
        before = oracles.sha256(bdf / "doc.txt")
        try:
            with RunLock(WORK, slots=1):
                rr = run_wine(pm, px, Path(f"{DISK}/bdfedit.exe"),
                              ["capability", f"{DISK}/doc.txt", f"{DISK}/doc.txt", MARKER],
                              cwd=bdf, log_dir=d / "logs", name=tag, timeout_s=90, debug=LIGHT, relay_exclude=None)
            events = parse_app_stdout(rr.stdout_path)
            evset = {e["event"] for e in events}
            announced = "SAVED" in evset
            doc = bdf / "doc.txt"
            o_changed = oracles.oracle_file_changed(doc, before, announced)
            o_mark = oracles.oracle_file_contains(doc, MARKER, announced)
            passed = rr.exit_code == 0 and o_changed.passed and o_mark.passed
            false_success = o_changed.false_success or o_mark.false_success
            detail = f"exit={rr.exit_code} events={sorted(evset)} changed={o_changed.passed} marker={o_mark.passed}"
        finally:
            pm.destroy_prefix(px)
        return {"passed": passed, "false_success": false_success, "detail": detail}

    print(f"[speculate] cible shcore.IsAppCompatModeEnabled (stub Wine {wi.version}), scénario « capability »")
    cands, verdict = candidate_answers("state-query", "BOOL", synthetic=True, has_output_pointer=False)
    print(f"[speculate] candidats autorisés par la table de sûreté : {[c.label for c in cands]} (S autorisé={verdict.s_allowed_lab})")
    res = search_answer("shcore.IsAppCompatModeEnabled", "state-query", "BOOL", True, False, evaluate)
    out = REPO / "results/speculate-demo.json"
    out.write_text(json.dumps(res.to_dict(), indent=1, ensure_ascii=False))
    print("\n=== essais ===")
    for t in res.trials:
        print(f"  {t['candidate']['label']:18s} -> passed={t['passed']} faux_succes={t['false_success']} | {t['detail']}")
    print("\n=== sélection ===")
    print("  réponse retenue :", res.selected["label"] if res.selected else "AUCUNE")
    print("  raison :", res.reason)
    print(f"\nrésultat : {out}")
    return 0


LIGHT = "warn+module,+seh,+loaddll"
if __name__ == "__main__":
    raise SystemExit(main())
