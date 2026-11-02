"""Tests de la découverte de réponse par recherche + oracle (logique de sélection, sans Wine)."""
from bdflab.speculate import candidate_answers, search_answer


def test_candidates_respect_safety_table():
    # requête d'état sans tampon : A et S autorisés
    c, v = candidate_answers("state-query", "BOOL", synthetic=True, has_output_pointer=False)
    labels = [x.strategy for x in c]
    assert "A" in labels and "S" in labels and v.s_allowed_lab
    # tampon de sortie : S interdit, seul A
    c2, v2 = candidate_answers("output-buffer", "BOOL", synthetic=True, has_output_pointer=True)
    assert [x.strategy for x in c2] == ["A"] and not v2.s_allowed_lab
    # sécurité : aucune réponse (ni A ni S)
    c3, v3 = candidate_answers("security", "BOOL", synthetic=True, has_output_pointer=False)
    assert c3 == []


def test_prefers_A_when_it_passes():
    res = search_answer("f", "state-query", "BOOL", True, False,
                        lambda c: {"passed": True, "false_success": False, "detail": ""})
    assert res.selected["strategy"] == "A"


def test_selects_S_only_when_A_fails():
    def ev(c):
        return {"passed": c.strategy == "S", "false_success": False, "detail": ""}
    res = search_answer("f", "state-query", "BOOL", True, False, ev)
    assert res.selected["strategy"] == "S"


def test_rejects_false_success():
    # un candidat "passe" mais par faux succès -> non retenu, escalade
    def ev(c):
        return {"passed": True, "false_success": True, "detail": ""}
    res = search_answer("f", "state-query", "BOOL", True, False, ev)
    assert res.selected is None
    assert "FAUX" in res.reason.upper() or "faux" in res.reason


def test_no_safe_answer_escalates():
    # output-buffer : seul A, et il échoue -> aucune sélection
    res = search_answer("f", "output-buffer", "BOOL", True, True,
                        lambda c: {"passed": False, "false_success": False, "detail": ""})
    assert res.selected is None


def test_unknown_return_type_tries_both_conventions():
    # type inconnu : A et S couvrent BOOL-style ET HRESULT-style ; l'oracle tranche
    c, v = candidate_answers("state-query", "", synthetic=True, has_output_pointer=False)
    labels = [x.label for x in c]
    assert any("convention BOOL" in l and l.startswith("A") for l in labels)
    assert any("convention HRESULT" in l and l.startswith("A") for l in labels)
    assert any("S:TRUE" in l for l in labels) and any("S:S_OK" in l for l in labels)
    # toujours aucun S sur tampon de sortie, même type inconnu
    c2, _ = candidate_answers("output-buffer", "", synthetic=True, has_output_pointer=True)
    assert all(x.strategy == "A" for x in c2) and len(c2) == 2


def test_unknown_type_hresult_function_picks_right_failure():
    # simule une fonction HRESULT inconnue : seul E_NOTIMPL est un vrai échec ; « 0 » serait un faux succès
    def ev(c):
        is_real_failure = (c.strategy == "A" and c.returns == 0x80004001)
        return {"passed": is_real_failure, "false_success": (c.strategy == "A" and c.returns == 0), "detail": ""}
    res = search_answer("f", "output-buffer", "", True, True, ev)
    assert res.selected is not None and res.selected["returns"] == 0x80004001
