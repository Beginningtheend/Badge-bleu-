#!/usr/bin/env python3
"""Généralisation — la question décisive : un correctif dérivé d'actions ENREGISTRÉES fonctionne-t-il sur des
actions que la VM « professeur » n'a JAMAIS enregistrées ? (« Windows comme professeur, Linux comme élève »)

Trois bras, mêmes actions tenues à l'écart (held-out : autres documents, Unicode, vide, 5000 lignes, scénarios
jamais utilisés pour dériver le correctif), chaque action dans un préfixe propre, jugée par oracle d'effet :

  1. RÈGLE dans la table de sûreté : absence déclarée (A) + capacité découverte par oracle (S). Le correctif ne
     rejoue aucune valeur ; la règle générale est dans le repli du programme (A) ou dans une propriété stable (S).
  2. VALEUR ENREGISTRÉE rejouée (contrôle négatif, HORS table de sûreté — le linter la refuse) : l'heure locale
     enregistrée dans la VM lors de la référence est rejouée telle quelle. Attendu : l'oracle faible (date
     plausible) est trompé, l'oracle fort (heure fraîche) et le garde-fou « sortie constante » la démasquent.
  3. RÈGLE synthétisée par la fonderie : une implémentation (la fonction, pas la valeur) proposée puis jugée par
     l'oracle sur les actions tenues à l'écart.

Rien n'est présumé : le verdict (generalizes / does-not-generalize / cannot-judge) sort de bdflab.generalize.
"""
from __future__ import annotations
import datetime as dt
import json, sys, shutil, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bdflab.wine_db import WineDB
from bdflab import pe_surface, oracles
from bdflab.shimgen import ShimSpec
from bdflab.fixgen import FixPlan, build_fix
from bdflab.safety import lint_shim
from bdflab.generalize import HeldOutRecord, generalization_verdict, capsule_section, annotate_capsule
from bdflab.capsule import load_capsule, lint_capsule, build_capsule
from bdflab.wine_runner import wine_info, PrefixManager, RunLock, run_wine
from bdflab.trace_parser import parse_app_stdout

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "testapps/bdfedit/bin/bdfedit.exe"
CAPSULE = REPO / "capsules/bdfedit-25205f9b77d4.capsule.toml"
WORK = Path("/home/user/_scratch/bdflab-work"); DISK = "C:/bdf"; LIGHT = "warn+module,+seh,+loaddll"
OUT = Path("/home/user/_scratch/generalization")

# --- apprentissage : UNE référence (edit, doc A, texte A) + UNE découverte S (capability, référence) ---
DERIVED_FROM = ["edit:reference", "capability:reference"]
A_HEAP = [ShimSpec("kernel32", "Heap32First", "A", "output-buffer", "BOOL", 0, 120),
          ShimSpec("kernel32", "Heap32Next", "A", "output-buffer", "BOOL", 0, 120)]
A_TZ = ShimSpec("kernel32", "SystemTimeToTzSpecificLocalTimeEx", "A", "output-buffer", "BOOL", 0, 120)
S_CAP = ShimSpec("shcore", "IsAppCompatModeEnabled", "S", "state-query", "BOOL", 1, None, tainted=True)

# bras 2 : la valeur que le « professeur » a enregistrée pendant l'exécution de référence, rejouée telle quelle
RECORDED = "2026-10-30 09:41:07"
REPLAY_C = r'''
int bdf_impl_SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *dtzi,
                                               const SYSTEMTIME *utc, LPSYSTEMTIME local)
{
    /* CONTRÔLE NÉGATIF : valeur ENREGISTRÉE dans la VM lors de la référence (2026-10-30 09:41:07), rejouée. */
    (void)dtzi; (void)utc;
    if (!local) return 0;
    local->wYear = 2026; local->wMonth = 10; local->wDayOfWeek = 5; local->wDay = 30;
    local->wHour = 9; local->wMinute = 41; local->wSecond = 7; local->wMilliseconds = 0;
    bdf_log("SystemTimeToTzSpecificLocalTimeEx", "F-replay", "recorded=2026-10-30 09:41:07");
    return 1;
}
'''
# bras 3 : la RÈGLE (fonction) proposée à la fonderie — délégation au non-Ex via le préfixe commun des structures
RULE_C = r'''
int bdf_impl_SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *dtzi,
                                               const SYSTEMTIME *utc, LPSYSTEMTIME local)
{
    TIME_ZONE_INFORMATION tzi;
    const TIME_ZONE_INFORMATION *p = NULL;
    if (dtzi) { memcpy(&tzi, dtzi, sizeof(tzi)); p = &tzi; }
    bdf_log("SystemTimeToTzSpecificLocalTimeEx", "IMPL", "delegate-to-non-Ex");
    return SystemTimeToTzSpecificLocalTime((TIME_ZONE_INFORMATION *)p, utc, local);
}
'''
F_REPLAY = ShimSpec("kernel32", "SystemTimeToTzSpecificLocalTimeEx", "F", "output-buffer", "BOOL", None, None,
                    tainted=True, note="CONTRÔLE NÉGATIF : valeur enregistrée rejouée, hors table de sûreté", custom_c=REPLAY_C)
I_RULE = ShimSpec("kernel32", "SystemTimeToTzSpecificLocalTimeEx", "IMPL", "output-buffer", "BOOL", None, None,
                  note="règle synthétisée (fonderie) : délégation", custom_c=RULE_C)

# --- actions tenues à l'écart (jamais utilisées pour dériver le correctif) ---
BIG = "\n".join(f"ligne {i} — contenu volumineux {'x' * (i % 40)}" for i in range(5000)) + "\n"
EDITS = [
    ("edit:doc-different", ["edit", f"{DISK}/d.txt", f"{DISK}/d.txt", "ajout-inedit-A1"], "alpha\nbeta\ngamma\n", "ajout-inedit-A1", "SAVE"),
    ("edit:unicode", ["edit", f"{DISK}/d.txt", f"{DISK}/d.txt", "été — ñandú — 日本語"], "première ligne é\nseconde ligne ü\n", "été", "SAVE"),
    ("edit:doc-vide", ["edit", f"{DISK}/d.txt", f"{DISK}/d.txt", "premiere-ligne-sur-vide"], "", "premiere-ligne-sur-vide", "SAVE"),
    ("edit:doc-5000-lignes", ["edit", f"{DISK}/d.txt", f"{DISK}/d.txt", "marque-fin-gros"], BIG, "marque-fin-gros", "SAVE"),
    ("capability:doc-different", ["capability", f"{DISK}/d.txt", f"{DISK}/d.txt", "cap-inedit-Z9"], "ref cap\n", "cap-inedit-Z9", "SAVE"),
]
OTHERS = [
    ("stats:jamais-derive", ["stats"], None, None, "STATS"),
    ("export-pdf:doc-different", ["export-pdf", f"{DISK}/d.txt", f"{DISK}/o.pdf"], "texte export inédit 4471\n", "4471", "PDF"),
    ("startup:temoin", ["idle", "1"], None, None, "EXIT"),
]

ARMS = [
    ("1-regle-table-surete", "règle dans la table de sûreté (A + S découvert)", A_HEAP + [A_TZ, S_CAP], EDITS + OTHERS),
    ("2-valeur-enregistree-rejouee", "valeur enregistrée rejouée (contrôle négatif, hors table)", A_HEAP + [S_CAP, F_REPLAY], EDITS),
    ("3-regle-synthetisee-fonderie", "règle synthétisée par la fonderie (fonction, pas valeur)", A_HEAP + [S_CAP, I_RULE], EDITS),
]


def run_action(pm, bf, pdf_dll, arm, i, name, args, doc, needle, kind) -> HeldOutRecord:
    px = pm.fresh_prefix(f"{arm[:1]}g{i}"); bdf = px / "drive_c" / "bdf"; bdf.mkdir(parents=True)
    shutil.copy2(bf.patched_exe, bdf / "bdfedit.exe")
    for g in bf.generated_dlls:
        shutil.copy2(g["binary_path"], bdf / g["proxy_dll_name"])
    shutil.copy2(pdf_dll, bdf / "bdfpdf.dll")
    before = None
    if doc is not None:
        (bdf / "d.txt").write_text(doc, encoding="utf-8"); before = oracles.sha256(bdf / "d.txt")
    try:
        started = dt.datetime.now()
        with RunLock(WORK, slots=1):
            rr = run_wine(pm, px, Path(f"{DISK}/bdfedit.exe"), args, cwd=bdf, log_dir=OUT / arm / "logs" / name.replace(":", "_"),
                          name=f"{arm[:1]}g{i}", timeout_s=120, debug=LIGHT, relay_exclude=None)
        ev = {e["event"]: e for e in parse_app_stdout(rr.stdout_path)}
        ors = [oracles.oracle_process_stable(rr.exit_code, rr.timed_out)]
        observed = {"stamp": ev.get("TZ", {}).get("stamp"), "tz_method": ev.get("TZ", {}).get("method")}
        if kind == "SAVE":
            d = bdf / "d.txt"; ann = "SAVED" in ev
            ors += [oracles.oracle_file_changed(d, before, ann), oracles.oracle_file_contains(d, needle, ann),
                    oracles.oracle_timestamp_plausible(d, ann),            # oracle FAIBLE (date plausible)
                    oracles.oracle_timestamp_fresh(d, started, 900, ann),  # oracle FORT (heure réelle de l'exécution)
                    oracles.oracle_reopen_consistent(d, needle)]
        elif kind == "STATS":
            ors.append(oracles.OracleResult("stats_degraded_cleanly", "STATS" in ev and rr.exit_code == 0,
                                            f"STATS={ev.get('STATS', {}).get('feature')}"))
        elif kind == "PDF":
            ors += [oracles.oracle_file_exists(bdf / "o.pdf"), oracles.oracle_pdf_text(bdf / "o.pdf", needle)]
        elif kind == "EXIT":
            ors.append(oracles.OracleResult("app_exit", ev.get("EXIT", {}).get("code") == "0", f"EXIT={ev.get('EXIT', {}).get('code')}"))
        weak = [o for o in ors if o.name != "timestamp_fresh"]
        observed["weak_passed"] = all(o.passed for o in weak)
        observed["weak_false_success"] = any(o.false_success for o in weak)
        rec = HeldOutRecord(name, all(o.passed for o in ors), any(o.false_success for o in ors), rr.exit_code,
                            [(o.name, o.passed) for o in ors], observed)
        fails = [(o.name, o.detail) for o in ors if not o.passed]
        print(f"    {name:28s} {'PASS' if rec.passed else 'FAIL'}{' [FAUX SUCCÈS]' if rec.false_success else ''} "
              f"exit={rr.exit_code} stamp={observed['stamp']} {fails or ''}")
        return rec
    finally:
        pm.destroy_prefix(px)


def main() -> int:
    db = WineDB(REPO / "data/wine-11.0"); wi = wine_info(); s = pe_surface.analyze(EXE, db)
    pm = PrefixManager(WORK, wi); pm.ensure_template()
    shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir(parents=True)
    pdf_dll = REPO / "catalogue/bdfpdf.dll"
    # la chaîne normale refuse le bras 2 : preuve par le linter (F sur tampon de sortie = F-forbidden)
    gate = lint_shim("B", "output-buffer", "F", True, True, None, None, "experimental", persistent_disposable=True)
    safety_gate = [i.to_dict() for i in gate]
    print("garde-fou de la table de sûreté pour le bras 2 :", [i.code for i in gate])
    results = {"derived_from": DERIVED_FROM, "recorded_value_replayed": RECORDED, "safety_gate_for_arm_2": safety_gate,
               "wine": wi.version, "arms": []}
    for arm, label, shims, actions in ARMS:
        print(f"\n=== bras {arm} : {label} ===")
        plan = FixPlan(identity={}, problems=[], declarative=[], shims=shims, rejected=[], notes=[])
        t0 = time.time(); bf = build_fix(plan, EXE, OUT / arm / "fix", s, catalogue_dir=REPO / "catalogue")
        gen_s = round(time.time() - t0, 2)
        recs = [run_action(pm, bf, pdf_dll, arm, i, *a) for i, a in enumerate(actions, 1)]
        strong = generalization_verdict(DERIVED_FROM, recs, input_dependent_key="stamp")
        weak_recs = [HeldOutRecord(r.action, r.observed["weak_passed"], r.observed["weak_false_success"], r.exit_code, r.oracles, {})
                     for r in recs]
        weak = generalization_verdict(DERIVED_FROM, weak_recs)   # oracle faible, sans garde-fou « sortie constante »
        print(f"  -> verdict oracle FORT  : {strong['verdict']} ({strong['passed']}/{strong['held_out_count']}, "
              f"{strong['false_success']} faux succès, sortie constante={strong['constant_output_suspect']}) — {strong['reasons'][0]}")
        print(f"  -> verdict oracle FAIBLE: {weak['verdict']} ({weak['passed']}/{weak['held_out_count']}, {weak['false_success']} faux succès)")
        results["arms"].append({"arm": arm, "label": label, "shims": [sh.to_dict() for sh in shims], "generation_seconds": gen_s,
                                "records": [r.to_dict() for r in recs], "verdict_strong_oracle": strong, "verdict_weak_oracle": weak})
    # capsule du programme COURANT : l'ancienne capsule (expérience A/B/C) décrit un binaire antérieur (sans
    # l'import de capacité) ; on émet donc une capsule pour l'identité exacte du binaire testé, avec les shims du
    # bras 1, la validation sur actions tenues à l'écart et la section [generalization] — puis on la linte.
    old = load_capsule(CAPSULE)
    ident = pe_surface.identity_of(s)
    v1 = results["arms"][0]["verdict_strong_oracle"]
    recs1 = results["arms"][0]["records"]
    contracts = [{"kind": "dll-provide", "dll": "bdfpdf", "source": "catalogue:bdfpdf", "sha256": oracles.sha256(pdf_dll), "mode": "native"}]
    cap = build_capsule(ident, wi.version, old["runtime"]["polyre"], contracts, [sh.to_dict() for sh in ARMS[0][2]],
                        [r["action"] for r in recs1], {r["action"].replace(":", "_"): {"passed": r["passed"], "false_success": r["false_success"]} for r in recs1},
                        runs=1, machines=1, status="experimental", synthetic=True)
    cap.notes = ["validation = actions tenues à l'écart (généralisation), 1 exécution chacune dans un préfixe propre ; "
                 "l'expérience A/B/C à 2 exécutions porte sur le binaire antérieur (capsule " + CAPSULE.name + ")"]
    new_cap = REPO / "capsules" / f"bdfedit-{ident['sha256'][:12]}.capsule.toml"
    cap.dump(new_cap)
    annotate_capsule(new_cap, capsule_section(v1, "strong (timestamp_fresh + garde-fou sortie constante)",
                                             note="mesuré par tools/demo_generalization.py ; programme synthétique"))
    lint = lint_capsule(load_capsule(new_cap))
    results["capsule"] = {"path": str(new_cap.relative_to(REPO)), "previous_capsule_binary": old["identity"]["sha256"][:12],
                          "lint_ok": lint.ok, "errors": lint.errors, "warnings": lint.warnings}
    print(f"\ncapsule émise avec [generalization] : {new_cap.name} ; lint ok={lint.ok} erreurs={lint.errors} avert.={len(lint.warnings)}")
    (REPO / "results/generalization-demo.json").write_text(json.dumps(results, indent=1, ensure_ascii=False))
    print("\n=== RÉSUMÉ ===")
    for a in results["arms"]:
        vs, vw = a["verdict_strong_oracle"], a["verdict_weak_oracle"]
        print(f"  {a['arm']:32s} fort={vs['verdict']:20s} faible={vw['verdict']:20s} ({vs['passed']}/{vs['held_out_count']} fort, {vw['passed']}/{vw['held_out_count']} faible)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
