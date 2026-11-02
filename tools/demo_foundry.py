#!/usr/bin/env python3
"""Démo de la fonderie (idée n°11) : deux implémentations PROPOSÉES de SystemTimeToTzSpecificLocalTimeEx.

  (a) correcte : délègue à SystemTimeToTzSpecificLocalTime (préfixe commun des structures) -> doit être ACCEPTÉE
  (b) fausse   : annonce le succès (TRUE) sans remplir la sortie -> horodatage « 0000-00-00 » -> doit être REJETÉE

L'oracle d'effet (fichier correct + horodatage plausible) est le seul juge. Le proposant peut être un
humain ou un modèle hors ligne ; à l'exécution il n'y a aucune IA.
"""
from __future__ import annotations
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bdflab.wine_db import WineDB
from bdflab import pe_surface, oracles
from bdflab.shimgen import ShimSpec
from bdflab.foundry import Proposal, verify_proposal
from bdflab.wine_runner import wine_info, PrefixManager, RunLock, run_wine
from bdflab.trace_parser import parse_app_stdout

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "testapps/bdfedit/bin/bdfedit.exe"
WORK = Path("/home/user/_scratch/bdflab-work")
MARKER = "foundry-marker-4420"
DISK = "C:/bdf"
LIGHT = "warn+module,+seh,+loaddll"

CORRECT = r'''
int bdf_impl_SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *dtzi,
                                               const SYSTEMTIME *utc, LPSYSTEMTIME local)
{
    TIME_ZONE_INFORMATION tzi;
    const TIME_ZONE_INFORMATION *p = NULL;
    if (dtzi) { memcpy(&tzi, dtzi, sizeof(tzi)); p = &tzi; }   /* préfixe commun des deux structures */
    bdf_log("SystemTimeToTzSpecificLocalTimeEx", "IMPL", "delegate-to-non-Ex");
    return SystemTimeToTzSpecificLocalTime((TIME_ZONE_INFORMATION *)p, utc, local);
}
'''
WRONG = r'''
int bdf_impl_SystemTimeToTzSpecificLocalTimeEx(const DYNAMIC_TIME_ZONE_INFORMATION *dtzi,
                                               const SYSTEMTIME *utc, LPSYSTEMTIME local)
{
    (void)dtzi; (void)utc; (void)local;
    bdf_log("SystemTimeToTzSpecificLocalTimeEx", "IMPL", "FAKE-success-without-filling-output");
    return 1;   /* « réussit » sans écrire la sortie : le programme horodatera 0000-00-00 */
}
'''


def main() -> int:
    db = WineDB(REPO / "data/wine-11.0"); wi = wine_info()
    s = pe_surface.analyze(EXE, db)
    pm = PrefixManager(WORK, wi); pm.ensure_template()
    # base : les autres stubs en absence déclarée, pour que seul TzEx soit en jeu
    base = [ShimSpec("kernel32", "Heap32First", "A", "output-buffer", "BOOL", 0, 120),
            ShimSpec("kernel32", "Heap32Next", "A", "output-buffer", "BOOL", 0, 120),
            ShimSpec("shcore", "IsAppCompatModeEnabled", "A", "state-query", "BOOL", 0, 120)]
    work = Path("/home/user/_scratch/foundry"); shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
    n = {"i": 0}

    def run_scenario(d, bf):
        n["i"] += 1
        tag = f"foundry{n['i']}"
        px = pm.fresh_prefix(tag)
        bdf = px / "drive_c" / "bdf"; bdf.mkdir(parents=True)
        shutil.copy2(bf.patched_exe, bdf / "bdfedit.exe")
        for g in bf.generated_dlls:
            shutil.copy2(g["binary_path"], bdf / g["proxy_dll_name"])
        doc = bdf / "doc.txt"; doc.write_text("reference\n", encoding="utf-8"); before = oracles.sha256(doc)
        try:
            with RunLock(WORK, slots=1):
                rr = run_wine(pm, px, Path(f"{DISK}/bdfedit.exe"), ["edit", f"{DISK}/doc.txt", f"{DISK}/doc.txt", MARKER],
                              cwd=bdf, log_dir=d / "logs", name=tag, timeout_s=90, debug=LIGHT, relay_exclude=None)
            ev = {e["event"]: e for e in parse_app_stdout(rr.stdout_path)}
            announced = "SAVED" in ev
            ors = [oracles.oracle_process_stable(rr.exit_code, rr.timed_out),
                   oracles.oracle_file_changed(doc, before, announced),
                   oracles.oracle_file_contains(doc, MARKER, announced),
                   oracles.oracle_timestamp_plausible(doc, announced),
                   oracles.oracle_reopen_consistent(doc, MARKER)]
            # information : par quel chemin le programme a horodaté (ex = implémentation proposée utilisée)
            method = ev.get("TZ", {}).get("method", "?"); stamp = ev.get("TZ", {}).get("stamp", "?")
            ors.append(oracles.OracleResult("tz_method_info", True, f"method={method} stamp={stamp}", kind="effect"))
        finally:
            pm.destroy_prefix(px)
        return ors, announced

    verdicts = []
    for author, src, label in [("offline-model (proposition correcte)", CORRECT, "correcte"),
                               ("offline-model (proposition fausse : succès sans sortie)", WRONG, "fausse")]:
        prop = Proposal("kernel32", "SystemTimeToTzSpecificLocalTimeEx", "BOOL", "output-buffer", author, src,
                        rationale="délégation au non-Ex" if label == "correcte" else "retourne TRUE sans remplir")
        v = verify_proposal(prop, base, EXE, s, work, run_scenario)
        verdicts.append(v.to_dict())
        print(f"\n=== proposition {label} ===")
        print("  verdict :", "ACCEPTÉE" if v.accepted else "REJETÉE", "| faux succès :", v.false_success)
        print("  oracles :", v.detail)
        print("  note    :", v.note)
    out = REPO / "results/foundry-demo.json"
    out.write_text(json.dumps(verdicts, indent=1, ensure_ascii=False))
    print(f"\nrésultat : {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
