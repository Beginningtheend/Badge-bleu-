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


FIXTURE_ALLOWED_CLASSES = {"state-query", "local-mutation"}   # v0.1 : retours scalaires seulement


def fixture_stability(fixture: dict) -> tuple[bool, str]:
    """Règle du professeur (RESULTATS §8.10) : une valeur enregistrée n'est admissible comme RÈGLE (F) que si le
    professeur l'a observée IDENTIQUE sous au moins deux entrées/états distincts. Des observations qui diffèrent
    = une valeur dépendante de l'entrée, pas une règle -> aucun candidat F (la fonderie prend le relais).

    Format : ``fixture["observations"] = [{"input": str, "returns": int, "last_error": int|None}, ...]``
    (optionnel ; sans ce champ, format 0.1 à valeur unique : admise mais étiquetée « observation unique »).
    """
    obs = fixture.get("observations") or []
    if not obs:
        return True, "observation unique : stabilité non établie par le professeur"
    inputs = {str(o.get("input")) for o in obs}
    outs = {(o.get("returns"), o.get("last_error")) for o in obs}
    if len(inputs) < 2:
        return False, f"{len(obs)} observation(s) sous une seule entrée : stabilité non établie"
    if len(outs) != 1:
        return False, (f"sorties différentes sous {len(inputs)} entrées distinctes : valeur dépendante de l'entrée, "
                       f"pas une règle (voie : fonderie)")
    return True, f"stable : même sortie sous {len(inputs)} entrées distinctes"


def candidate_answers(api_class: str, ret_type: str, synthetic: bool, has_output_pointer: bool,
                      fixture: dict | None = None):
    """Énumère les réponses candidates AUTORISÉES par la table de sûreté pour cette fonction.

    ``fixture`` : réponse RÉELLE distillée sur un Windows (cf. RECHERCHE-graal-2026.md §8), de la forme
    {"returns": int, "last_error": int|None, "source": str}. Si présente et si la classe d'API l'autorise
    (requête d'état / mutation locale ; pas de tampon de sortie en v0.1), elle devient le PREMIER candidat,
    stratégie « F » (fidèle). Elle n'autorise rien de plus que S et reste jugée par l'oracle d'effet.
    """
    v = safety_evaluate("B", api_class, has_output_pointer, synthetic, persistent_disposable=synthetic)
    rt = (ret_type or "").upper()
    unknown = rt in ("", "UNKNOWN", "?")
    cands: list[Candidate] = []
    if fixture and api_class in FIXTURE_ALLOWED_CLASSES and not has_output_pointer and v.s_allowed_lab:
        stable, why = fixture_stability(fixture)
        if stable:
            obs = fixture.get("observations") or []
            ret = obs[0].get("returns", 0) if obs else fixture.get("returns", 0)
            le = obs[0].get("last_error") if obs else fixture.get("last_error")
            cands.append(Candidate("F", ret, le, f"F:fixture({fixture.get('source', 'windows')}; {why})"))
    if v.a_allowed:
        if rt == "HRESULT":
            cands.append(Candidate("A", E_NOTIMPL, None, "A:E_NOTIMPL"))
        elif rt == "LSTATUS":
            cands.append(Candidate("A", ERROR_CALL_NOT_IMPLEMENTED, None, "A:ERROR_CALL_NOT_IMPLEMENTED"))
        elif rt == "NTSTATUS":
            cands.append(Candidate("A", 0xC0000002, None, "A:STATUS_NOT_IMPLEMENTED"))
        elif unknown:
            # Type de retour INCONNU (cas fréquent : la plupart des @ stub n'ont pas de prototype public).
            # Grille des deux conventions d'échec : BOOL-style (0 + last_error) ET HRESULT-style (E_NOTIMPL),
            # car « 0 » serait un SUCCÈS si la fonction renvoie un HRESULT. L'oracle tranche.
            cands.append(Candidate("A", 0, ERROR_CALL_NOT_IMPLEMENTED, "A:0+last_error=120 (convention BOOL)"))
            cands.append(Candidate("A", E_NOTIMPL, None, "A:E_NOTIMPL (convention HRESULT)"))
        else:
            cands.append(Candidate("A", 0, ERROR_CALL_NOT_IMPLEMENTED, "A:0+last_error=120"))
    if v.s_allowed_lab:
        if rt == "HRESULT":
            cands.append(Candidate("S", 0, None, "S:S_OK"))
        elif rt in ("BOOL", "WINBOOL", "INT", "INT32", "LONG"):
            cands.append(Candidate("S", 1, None, "S:TRUE"))
        elif unknown:
            # grille des deux conventions de succès : TRUE (BOOL) et S_OK (HRESULT/NTSTATUS)
            cands.append(Candidate("S", 1, None, "S:TRUE (convention BOOL)"))
            cands.append(Candidate("S", 0, None, "S:S_OK (convention HRESULT)"))
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
                  evaluate_fn, first_strategy: str | None = None, fixture: dict | None = None) -> SearchResult:
    """Essaie chaque candidat via ``evaluate_fn(candidate) -> {passed, false_success, detail}`` et choisit.

    Préférence : A qui passe > S qui passe (sans faux succès). Aucun candidat retenu si tous échouent
    ou si le seul qui « passe » le fait par faux succès (qui compte comme échec).
    """
    cands, v = candidate_answers(api_class, ret_type, synthetic, has_output_pointer, fixture=fixture)
    # indice statique (analyse des branches) : essayer d'abord la stratégie prédite, SANS jamais ajouter
    # de candidat que la table de sûreté n'autorise pas (l'indice ordonne, il n'autorise rien).
    # Une fixture (réponse Windows enregistrée) garde toujours la première place.
    if first_strategy in ("A", "S"):
        cands = sorted(cands, key=lambda c: (0 if c.strategy == "F" else 1, 0 if c.strategy == first_strategy else 1))
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
    if selected is None:
        for t in passing:
            if t.candidate["strategy"] == "F":
                selected = t
                reason = (f"aucune réponse A ne passe ; « {t.candidate['label']} » — réponse RÉELLE distillée sur Windows — "
                          f"fait passer l'oracle d'effet, sans faux succès (préférée à un succès fabriqué)")
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
