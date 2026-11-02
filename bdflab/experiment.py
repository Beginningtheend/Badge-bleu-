"""Harnais d'expérience — protocole phase 0 du rapport, réduit à 3 bras (mission §6).

Trois configurations, chacune jouée sur plusieurs scénarios, au moins deux fois, dans des préfixes
Wine propres et jetables :

  A  Wine standard                 exécutable d'origine, sans rien ajouter (référence)
  B  Wine + correctif généré       bundle produit automatiquement par le labo
  C  Wine + correctif manuel        DLL de compatibilité écrite à la main (référence humaine)

Mesures : scénarios réussis, faux succès, régressions, temps de génération, CPU/RAM, reproductibilité.
Aucun gain n'est revendiqué sans mesure. Un succès annoncé par le programme sans fichier correct est
classé « faux succès » (oracles d'effet, :mod:`oracles`).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .wine_db import WineDB
from .wine_runner import (PrefixManager, RunLock, run_wine, wine_info, preflight,
                          DEFAULT_DEBUG, DEFAULT_RELAY_EXCLUDE)
from .trace_parser import parse_wine_log, parse_app_stdout
from . import pe_surface, fixgen, oracles
from .oracles import OracleResult, ScenarioOutcome

LIGHT_DEBUG = "warn+module,+seh,+loaddll"
DISKDIR = "C:/bdf"

MARKER_EDIT = "bdflab-marque-modif-9173"


# --- définition des scénarios ------------------------------------------------------------------

SCENARIOS = [
    {"name": "startup", "args": ["idle", "2"], "needs_pdf": False,
     "doc": None, "exercises": "démarrage stable (témoin, ne dépend d'aucune API absente)"},
    {"name": "edit-save-reopen", "args": ["edit", f"{DISKDIR}/doc.txt", f"{DISKDIR}/doc.txt", MARKER_EDIT],
     "needs_pdf": False, "doc": "contenu de reference\nligne deux\n",
     "exercises": "modification + enregistrement + réouverture ; dépend de SystemTimeToTzSpecificLocalTimeEx"},
    {"name": "stats-degrade", "args": ["stats"], "needs_pdf": False, "doc": None,
     "exercises": "fonctionnalité diagnostic ; dépend de Heap32First (dégradation propre attendue)"},
    {"name": "export-pdf", "args": ["export-pdf", f"{DISKDIR}/doc.txt", f"{DISKDIR}/out.pdf"],
     "needs_pdf": True, "doc": "contenu a exporter\n" + MARKER_EDIT + "\n",
     "exercises": "export PDF ; dépend de la DLL bdfpdf (classe A, fournie par le catalogue)"},
]


def build_oracles(scenario: dict, bdf_dir: Path, events: list[dict], exit_code: int | None,
                  timed_out: bool, before_sha: str | None) -> ScenarioOutcome:
    name = scenario["name"]
    ev_by = {e["event"]: e for e in events}
    announced_saved = "SAVED" in ev_by
    announced_export = "EXPORTED" in ev_by
    ors: list[OracleResult] = [oracles.oracle_process_stable(exit_code, timed_out)]
    if name == "startup":
        ors.append(OracleResult("app_reported_exit", ev_by.get("EXIT", {}).get("code") == "0",
                                f"événement EXIT code={ev_by.get('EXIT', {}).get('code')}", kind="effect"))
    elif name == "edit-save-reopen":
        doc = bdf_dir / "doc.txt"
        ors.append(oracles.oracle_file_changed(doc, before_sha, announced_saved))
        ors.append(oracles.oracle_file_contains(doc, MARKER_EDIT, announced_saved))
        ors.append(oracles.oracle_file_contains(doc, "saved-at", announced_saved))
        ors.append(oracles.oracle_reopen_consistent(doc, MARKER_EDIT))
    elif name == "stats-degrade":
        st = ev_by.get("STATS", {})
        feat = st.get("feature", "")
        # succès = le programme a survécu et a signalé la fonctionnalité (dégradée proprement ou disponible)
        ok = ("STATS" in ev_by) and (exit_code == 0) and (feat in {"available", "unavailable-degraded"})
        ors.append(OracleResult("stats_degraded_cleanly", ok,
                                f"STATS feature={feat!r} exit={exit_code}", kind="effect"))
    elif name == "export-pdf":
        pdf = bdf_dir / "out.pdf"
        ors.append(oracles.oracle_file_exists(pdf))
        ors.append(oracles.oracle_pdf_text(pdf, MARKER_EDIT))
    return ScenarioOutcome(scenario=name, oracles=ors,
                           app_announced_success=announced_saved or announced_export or (name in {"startup", "stats-degrade"} and exit_code == 0))


# --- une exécution -----------------------------------------------------------------------------

@dataclass
class RunRecord:
    config: str
    scenario: str
    run_idx: int
    exit_code: int | None
    timed_out: bool
    wall_s: float
    cpu_s: float
    max_rss_kb: int
    peak_rss_kb: int
    passed: bool
    false_success: bool
    oracles: list[dict]
    app_events: list[str]
    trace_summary: dict
    stdout_path: str
    log_path: str
    produced_sha: dict
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _stage(bundle: dict, scenario: dict, bdf_dir: Path) -> str | None:
    """Dépose dans bdf_dir les fichiers nécessaires au scénario pour la configuration ; renvoie le sha du doc avant."""
    bdf_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundle["exe"], bdf_dir / "bdfedit.exe")
    for dll in bundle.get("dlls", []):
        shutil.copy2(dll, bdf_dir / Path(dll).name)
    if scenario["needs_pdf"] and bundle.get("pdf_dll"):
        shutil.copy2(bundle["pdf_dll"], bdf_dir / Path(bundle["pdf_dll"]).name)
    before_sha = None
    if scenario["doc"]:
        doc = bdf_dir / "doc.txt"
        doc.write_text(scenario["doc"], encoding="utf-8")
        before_sha = oracles.sha256(doc)
    return before_sha


def run_scenario(pm: PrefixManager, work: Path, config: str, bundle: dict, scenario: dict, run_idx: int,
                 results_dir: Path, diagnostic: bool) -> RunRecord:
    name = scenario["name"]
    tag = f"{config}-{name}-r{run_idx}"
    px = pm.fresh_prefix(tag)
    bdf_dir = px / "drive_c" / "bdf"
    before_sha = _stage(bundle, scenario, bdf_dir)
    log_dir = results_dir / "runs" / tag
    debug = DEFAULT_DEBUG if diagnostic else LIGHT_DEBUG
    shim_log = log_dir / "shim.calls.log"
    log_dir.mkdir(parents=True, exist_ok=True)
    extra = {"BDFLAB_SHIM_LOG": str(shim_log)}
    try:
        with RunLock(work, slots=1):
            rr = run_wine(pm, px, Path(f"{DISKDIR}/bdfedit.exe"), scenario["args"], cwd=bdf_dir, log_dir=log_dir,
                          name=tag, timeout_s=90, debug=debug, extra_env=extra,
                          relay_exclude=DEFAULT_RELAY_EXCLUDE if diagnostic else None)
        events = parse_app_stdout(rr.stdout_path)
        ts = parse_wine_log(rr.stderr_path)
        # oracles (sur les fichiers produits, côté hôte)
        outcome = build_oracles(scenario, bdf_dir, events, rr.exit_code, rr.timed_out, before_sha)
        # empreintes des fichiers produits
        produced = {}
        for fn in ("doc.txt", "out.pdf"):
            fp = bdf_dir / fn
            if fp.is_file():
                produced[fn] = oracles.sha256(fp)
        # conserver une COPIE des fichiers produits comme preuve
        art = log_dir / "artifacts"
        art.mkdir(exist_ok=True)
        for fn in ("doc.txt", "out.pdf"):
            fp = bdf_dir / fn
            if fp.is_file():
                shutil.copy2(fp, art / fn)
        # gérer le volume des traces : relay compressé, trimé en preuve
        trimmed = _trim_trace(rr.stderr_path, ts, diagnostic)
        rec = RunRecord(config=config, scenario=name, run_idx=run_idx, exit_code=rr.exit_code, timed_out=rr.timed_out,
                        wall_s=rr.wall_s, cpu_s=round(rr.cpu_user_s + rr.cpu_sys_s, 3), max_rss_kb=rr.max_rss_kb_main,
                        peak_rss_kb=rr.peak_rss_kb_tree, passed=outcome.passed, false_success=outcome.false_success,
                        oracles=[o.to_dict() for o in outcome.oracles], app_events=[e["event"] for e in events],
                        trace_summary=_trace_brief(ts), stdout_path=str(Path(rr.stdout_path).relative_to(results_dir.parent)),
                        log_path=trimmed, produced_sha=produced, notes=rr.notes)
        return rec
    finally:
        pm.destroy_prefix(px)


def _trace_brief(ts) -> dict:
    return {
        "lines": ts.lines, "relay_calls": ts.relay_calls, "fatal": ts.fatal,
        "stub_calls": [{"module": s.module, "func": s.func, "addr": s.address, "line": s.line_no} for s in ts.stub_calls],
        "missing_impl_imports": [f"{m['mod']}.{m['func']}" for m in ts.missing_impl_imports],
        "missing_libraries": [m.get("lib") for m in ts.missing_libraries],
        "import_failures": ts.import_failures,
        "exceptions": [f"{e['code']}({e.get('name', '')})" for e in ts.exceptions][:12],
        "unhandled": ts.unhandled[:4],
        "dynamic_load_failures": ts.dynamic_load_failures,
    }


def _trim_trace(raw_log: str, ts, diagnostic: bool) -> str:
    """Réduit le volume : en mode diagnostic, garde une preuve (contexte du stub) et compresse le brut."""
    raw = Path(raw_log)
    if diagnostic and ts.stub_calls:
        ev = raw.with_suffix(".evidence.txt")
        lines = ["# Preuve extraite de la trace Wine (diagnostic). Appel(s) à une fonction non implémentée :\n"]
        for s in ts.stub_calls:
            lines.append(f"\n## {s.module}.{s.func} @ {s.address} (ligne {s.line_no})\n")
            lines.append("# derniers appels relay du même thread avant l'exception EXCEPTION_WINE_STUB :\n")
            lines += [c + "\n" for c in s.context[-12:]]
        ev.write_text("".join(lines), encoding="utf-8")
    # compresser le brut (relay volumineux) et supprimer l'original
    gz = raw.with_suffix(raw.suffix + ".gz")
    with raw.open("rb") as fi, gzip.open(gz, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    raw.unlink()
    return str(gz.relative_to(gz.parents[3])) if len(gz.parents) >= 4 else str(gz)


# --- matrice complète --------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    wine: dict
    started: str
    scenarios: list[str]
    configs: list[str]
    records: list[dict]
    gen_time_b_s: float
    gen_actions_b: list[str]
    manual_build_c_s: float
    comparison: dict
    capsule_path: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(records: list[RunRecord], configs: list[str], scenarios: list[str]) -> dict:
    by = {(r.config, r.scenario): [] for r in records}
    for r in records:
        by[(r.config, r.scenario)].append(r)
    table = {}
    for c in configs:
        passed = sum(1 for r in records if r.config == c and r.passed)
        total = sum(1 for r in records if r.config == c)
        fsucc = sum(1 for r in records if r.config == c and r.false_success)
        # reproductibilité : même verdict pass/fail sur les 2 runs d'un scénario
        repro = []
        for sc in scenarios:
            verdicts = [r.passed for r in records if r.config == c and r.scenario == sc]
            repro.append(len(set(verdicts)) == 1 and len(verdicts) >= 2)
        cpu = [r.cpu_s for r in records if r.config == c]
        rss = [r.peak_rss_kb for r in records if r.config == c]
        table[c] = {
            "runs": total, "scenario_passes": passed, "scenarios_distinct": len(scenarios),
            "false_success": fsucc,
            "reproducible": all(repro), "reproducible_detail": dict(zip(scenarios, repro)),
            "cpu_s_mean": round(statistics.mean(cpu), 3) if cpu else 0,
            "peak_rss_mb_mean": round(statistics.mean(rss) / 1024, 1) if rss else 0,
            "per_scenario": {sc: {"pass": sum(1 for r in records if r.config == c and r.scenario == sc and r.passed),
                                  "of": sum(1 for r in records if r.config == c and r.scenario == sc)}
                             for sc in scenarios},
        }
    # régressions : scénario réussi en A mais échoué en B ou C
    regressions = []
    for sc in scenarios:
        a_pass = all(r.passed for r in records if r.config == "A" and r.scenario == sc) and any(r.config == "A" and r.scenario == sc for r in records)
        for c in ("B", "C"):
            if c in configs:
                c_pass = all(r.passed for r in records if r.config == c and r.scenario == sc) and any(r.config == c and r.scenario == sc for r in records)
                if a_pass and not c_pass:
                    regressions.append({"scenario": sc, "config": c})
    return {"table": table, "regressions": regressions}
