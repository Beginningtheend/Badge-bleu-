"""Généralisation — la question décisive (RESULTATS §8.10, RECHERCHE §10 sexies) : un correctif dérivé d'actions
ENREGISTRÉES fonctionne-t-il sur des actions que le « professeur » (la VM Windows) n'a JAMAIS enregistrées ?

Ce module ne génère rien : il JUGE, à partir d'oracles d'effet obtenus sur des actions tenues à l'écart
(held-out : autres documents, autres entrées, autres scénarios), et rend un verdict en trois valeurs, jamais
présumé :

  generalizes          toutes les actions tenues à l'écart passent, 0 faux succès, ≥ min_actions
  does-not-generalize  au moins un échec, un faux succès, ou une sortie constante suspecte (récitation)
  cannot-judge         trop peu d'actions, ou des actions d'apprentissage comptées comme tenues à l'écart

Garde-fous :
  - disjonction : une action tenue à l'écart ne doit pas être une action d'apprentissage ;
  - portée : « new-inputs » (mêmes familles de scénario, entrées nouvelles) ou « new-inputs-and-new-scenarios » ;
  - sortie constante suspecte : si une fonction dont la sortie DOIT dépendre de l'entrée (temps, document)
    renvoie exactement la même chose sur toutes les actions, c'est la signature d'une valeur REJOUÉE
    (récitation du professeur), même quand un oracle faible ne voit rien. Une règle n'est pas une valeur.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable

VERDICTS = ("generalizes", "does-not-generalize", "cannot-judge")
SCOPES = ("new-inputs", "new-inputs-and-new-scenarios")


@dataclass
class HeldOutRecord:
    action: str                                   # ex. "edit:unicode" (famille:variante)
    passed: bool
    false_success: bool
    exit_code: int | None = None
    oracles: list = field(default_factory=list)   # [(nom, ok)]
    observed: dict = field(default_factory=dict)  # valeurs observées (ex. "stamp") pour les garde-fous

    @property
    def family(self) -> str:
        return family_of(self.action)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["family"] = self.family
        return d


def family_of(action: str) -> str:
    """« edit:unicode » -> « edit » (famille de scénario)."""
    return action.split(":", 1)[0]


def overlap(derived_from: Iterable[str], held_out: Iterable[str]) -> list[str]:
    """Actions « tenues à l'écart » qui sont en fait des actions d'apprentissage (violation de disjonction)."""
    d = set(derived_from)
    return [a for a in held_out if a in d]


def constant_output_suspect(values: Iterable) -> bool:
    """Vrai si ≥ 2 valeurs observées et toutes identiques : signature d'une valeur rejouée."""
    vals = [v for v in values if v not in (None, "", "?")]
    return len(vals) >= 2 and len(set(vals)) == 1


def generalization_verdict(derived_from: list[str], records: list[HeldOutRecord], min_actions: int = 3,
                           input_dependent_key: str | None = None) -> dict:
    """Verdict de généralisation sur des actions tenues à l'écart. Jamais présumé : trois valeurs."""
    reasons: list[str] = []
    actions = [r.action for r in records]
    ov = overlap(derived_from, actions)
    n = len(records)
    n_pass = sum(1 for r in records if r.passed)
    n_fs = sum(1 for r in records if r.false_success)
    learned = {family_of(a) for a in derived_from}
    new_families = sorted({r.family for r in records} - learned)
    suspect = bool(input_dependent_key) and constant_output_suspect(r.observed.get(input_dependent_key) for r in records)
    if ov:
        verdict = "cannot-judge"
        reasons.append(f"actions d'apprentissage comptées comme tenues à l'écart : {ov}")
    elif n == 0:
        verdict = "cannot-judge"
        reasons.append("aucune action tenue à l'écart")
    elif n_fs:
        verdict = "does-not-generalize"
        reasons.append(f"{n_fs} faux succès sur {n} action(s) jamais enregistrée(s)")
    elif n_pass < n:
        verdict = "does-not-generalize"
        reasons.append(f"{n - n_pass} échec(s) sur {n} action(s) jamais enregistrée(s)")
    elif suspect:
        verdict = "does-not-generalize"
        reasons.append(f"sortie « {input_dependent_key} » identique sur les {n} actions pour une fonction dépendante "
                       f"de l'entrée : valeur rejouée (récitation), pas une règle")
    elif n < min_actions:
        verdict = "cannot-judge"
        reasons.append(f"{n} action(s) tenue(s) à l'écart < {min_actions} : trop peu pour juger")
    else:
        verdict = "generalizes"
        reasons.append(f"{n_pass}/{n} actions jamais enregistrées réussies, 0 faux succès" +
                       (f", {len(new_families)} famille(s) de scénario jamais apprise(s) : {new_families}"
                        if new_families else ", entrées nouvelles seulement"))
    scope = "new-inputs-and-new-scenarios" if new_families else "new-inputs"
    return {"verdict": verdict, "scope": scope, "derived_from": list(derived_from), "held_out": actions,
            "held_out_count": n, "passed": n_pass, "false_success": n_fs, "new_families": new_families,
            "constant_output_suspect": suspect, "input_dependent_key": input_dependent_key or "", "reasons": reasons}


def capsule_section(verdict: dict, oracle_strength: str, note: str = "") -> dict:
    """Section TOML « [generalization] » d'une capsule (sans valeur nulle : TOML ne les accepte pas)."""
    sec = {"verdict": verdict["verdict"], "scope": verdict["scope"], "derived_from": verdict["derived_from"],
           "held_out": verdict["held_out"], "held_out_count": verdict["held_out_count"],
           "passed": verdict["passed"], "false_success": verdict["false_success"],
           "new_families": verdict["new_families"], "constant_output_suspect": verdict["constant_output_suspect"],
           "oracle_strength": oracle_strength, "reasons": verdict["reasons"]}
    if verdict.get("input_dependent_key"):
        sec["input_dependent_key"] = verdict["input_dependent_key"]
    if note:
        sec["note"] = note
    return sec


def annotate_capsule(path: Path, section: dict) -> dict:
    """Ajoute/remplace « [generalization] » dans une capsule existante et la réécrit (en-tête conservé)."""
    import tomli_w
    from .capsule import load_capsule, CAPSULE_HEADER
    obj = load_capsule(path)
    obj["generalization"] = section
    Path(path).write_text(CAPSULE_HEADER + tomli_w.dumps(obj), encoding="utf-8")
    return obj
