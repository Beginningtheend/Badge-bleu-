"""Fonderie de shims (idée n°11 du carnet) : toute implémentation PROPOSÉE doit passer l'oracle d'effet.

Une implémentation d'une fonction manquante peut être proposée par un humain ou par un modèle hors ligne.
La fonderie ne fait AUCUNE confiance à la proposition : elle la compile dans la DLL de compatibilité,
rejoue le scénario dans un préfixe propre, et n'ACCEPTE que si tous les oracles d'effet passent sans faux
succès. Une proposition acceptée est marquée « vérifiée par oracle d'effet » ; une proposition qui
annonce le succès mais corrompt le résultat est REJETÉE. À l'exécution, aucune IA : seul le code accepté
et signé tourne. (Le modèle n'est qu'un proposant parmi d'autres ; l'oracle est le juge.)
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
import shutil

from .shimgen import ShimSpec
from .fixgen import FixPlan, build_fix


@dataclass
class Proposal:
    dll: str
    func: str
    ret_type: str
    api_class: str
    author: str                # "human" | "offline-model" | ...
    custom_c: str              # définition complète de bdf_impl_<func>
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FoundryVerdict:
    proposal: dict
    accepted: bool
    oracles: list[dict]
    false_success: bool
    detail: str
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def verify_proposal(proposal: Proposal, base_shims: list[ShimSpec], exe: Path, surface, work_dir: Path,
                    run_scenario_fn) -> FoundryVerdict:
    """Compile la proposition dans le bundle, puis ``run_scenario_fn(bundle_dir) -> (oracles, announced)``.

    ``oracles`` : liste d'OracleResult ; ``announced`` : le programme a-t-il annoncé le succès.
    Acceptée ssi tous les oracles passent ET aucun faux succès.
    """
    spec = ShimSpec(proposal.dll, proposal.func, "IMPL", proposal.api_class, proposal.ret_type, None, None,
                    note=f"proposée par {proposal.author}", custom_c=proposal.custom_c)
    plan = FixPlan(identity={}, problems=[], declarative=[], shims=base_shims + [spec], rejected=[], notes=[])
    d = work_dir / f"proposal-{proposal.author}-{proposal.func}"
    shutil.rmtree(d, ignore_errors=True)
    try:
        bf = build_fix(plan, exe, d / "fix", surface)
    except Exception as exc:
        return FoundryVerdict(proposal.to_dict(), False, [], False, f"compilation refusée : {exc}"[:400],
                              "proposition rejetée avant exécution (ne compile pas)")
    oracles, announced = run_scenario_fn(d, bf)
    ok = all(o.passed for o in oracles) and bool(oracles)
    fs = announced and any(o.false_success for o in oracles)
    accepted = ok and not fs
    detail = "; ".join(f"{o.name}={'ok' if o.passed else 'ÉCHEC'}" for o in oracles)
    note = ("ACCEPTÉE : effets vérifiés par oracle indépendant, sans faux succès ; éligible à la capsule "
            "(aucune IA à l'exécution)") if accepted else (
           "REJETÉE : succès annoncé mais effet absent/incorrect (faux succès)" if fs else
           "REJETÉE : l'oracle d'effet échoue")
    return FoundryVerdict(proposal.to_dict(), accepted, [o.to_dict() for o in oracles], fs, detail, note)
