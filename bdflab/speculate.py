"""Découverte automatique de la réponse d'un stub par recherche + oracle (« OracleForge » au niveau réponse).

Au lieu qu'un humain décide quelle valeur une fonction manquante doit renvoyer, le labo ESSAIE toutes
les réponses SÛRES autorisées par la table de sûreté, rejoue le scénario pour chacune dans un préfixe
propre, et SÉLECTIONNE celle dont l'effet est vérifié par un oracle indépendant — en préférant toujours
la stratégie A (absence déclarée, aucune fabrication) et en ne retenant un succès fabriqué (S) que si
A ne suffit pas, que la table de sûreté l'autorise, et qu'aucun faux succès ni corruption n'est observé.

C'est la moitié « active » de la Fidélité dirigée par le binaire : la réponse optimiste n'est plus
devinée ni codée à la main, elle est DÉCOUVERTE et prouvée par l'effet.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .safety import evaluate as safety_evaluate, ERROR_CALL_NOT_IMPLEMENTED, E_NOTIMPL


@dataclass
class Candidate:
    strategy: str          # "A" (absence déclarée) ou "S" (succès fabriqué)
    returns: object
    last_error: object
    label: str

    def to_dict(self) -> dict:
        return asdict(self)


def candidate_answers(api_class: str, ret_type: str, synthetic: bool, has_output_pointer: bool):
    """Énumère les réponses candidates AUTORISÉES par la table de sûreté pour cette fonction."""
    v = safety_evaluate("B", api_class, has_output_pointer, synthetic, persistent_disposable=synthetic)
    rt = (ret_type or "").upper()
    cands: list[Candidate] = []
    if v.a_allowed:
        if rt == "HRESULT":
            cands.append(Candidate("A", E_NOTIMPL, None, "A:E_NOTIMPL"))
        elif rt == "LSTATUS":
            cands.append(Candidate("A", ERROR_CALL_NOT_IMPLEMENTED, None, "A:ERROR_CALL_NOT_IMPLEMENTED"))
        elif rt == "NTSTATUS":
            cands.append(Candidate("A", 0xC0000002, None, "A:STATUS_NOT_IMPLEMENTED"))
        else:
            cands.append(Candidate("A", 0, ERROR_CALL_NOT_IMPLEMENTED, "A:0+last_error=120"))
    if v.s_allowed_lab:
        if rt == "HRESULT":
            cands.append(Candidate("S", 0, None, "S:S_OK"))
        elif rt in ("BOOL", "WINBOOL", "INT", "INT32", "LONG"):
            cands.append(Candidate("S", 1, None, "S:TRUE"))
        else:
            cands.append(Candidate("S", 1, None, "S:nonzero"))
    return cands, v


@dataclass
class Trial:
    candidate: dict
    passed: bool
    false_success: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SearchResult:
    func: str
    api_class: str
    selected: dict | None
    reason: str
    trials: list
    safety: dict

    def to_dict(self) -> dict:
        return asdict(self)


def search_answer(func: str, api_class: str, ret_type: str, synthetic: bool, has_output_pointer: bool,
                  evaluate_fn) -> SearchResult:
    """Essaie chaque candidat via ``evaluate_fn(candidate) -> {passed, false_success, detail}`` et choisit.

    Préférence : A qui passe > S qui passe (sans faux succès). Aucun candidat retenu si tous échouent
    ou si le seul qui « passe » le fait par faux succès (qui compte comme échec).
    """
    cands, v = candidate_answers(api_class, ret_type, synthetic, has_output_pointer)
    trials: list[Trial] = []
    for c in cands:
        r = evaluate_fn(c)
        trials.append(Trial(c.to_dict(), bool(r.get("passed")), bool(r.get("false_success")), r.get("detail", "")))

    passing = [t for t in trials if t.passed and not t.false_success]
    selected = None
    reason = ""
    for t in passing:
        if t.candidate["strategy"] == "A":
            selected = t
            reason = "la stratégie A (absence déclarée) fait passer l'oracle : préférée, aucune valeur fabriquée"
            break
    if selected is None and passing:
        selected = passing[0]
        reason = (f"aucune réponse A ne passe ; « {selected.candidate['label']} » (succès fabriqué) fait passer "
                  f"l'oracle d'effet, sans faux succès, et la table de sûreté l'autorise pour « {api_class} » "
                  f"(teinté et journalisé)")
    if selected is None:
        if any(t.passed and t.false_success for t in trials):
            reason = "un candidat « passe » mais par FAUX SUCCÈS (effet non constaté) : rejeté ; escalade nécessaire"
        else:
            reason = "aucune réponse sûre ne fait passer l'oracle : escalade nécessaire (classe C)"
    return SearchResult(func=func, api_class=api_class, selected=(selected.candidate if selected else None),
                        reason=reason, trials=[t.to_dict() for t in trials], safety=v.to_dict())
