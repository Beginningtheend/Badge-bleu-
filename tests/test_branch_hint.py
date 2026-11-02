"""Tests de la pré-réponse par analyse des branches (sur l'exécutable de test compilé)."""
from pathlib import Path
import pytest
from bdflab import branch_hint
from bdflab.speculate import search_answer

EXE = Path(__file__).resolve().parent.parent / "testapps/bdfedit/bin/bdfedit.exe"
pytestmark = pytest.mark.skipif(not EXE.exists(), reason="bdfedit.exe non compilé")


def test_capability_call_predicts_nonzero_nominal():
    h = branch_hint.analyze(EXE, "shcore", "IsAppCompatModeEnabled")
    assert h.call_sites >= 1 and h.tested
    # le programme renonce (code 2) si la valeur est nulle -> non-nul garde le chemin nominal -> S d'abord
    assert h.predicted_nonzero_nominal is True
    assert h.preferred_strategy_first() == "S"


def test_tz_call_is_tested_and_branched():
    h = branch_hint.analyze(EXE, "kernel32", "SystemTimeToTzSpecificLocalTimeEx")
    assert h.call_sites >= 1 and h.tested
    assert any("test" in e for e in h.evidence)


def test_unknown_import_gives_no_hint():
    h = branch_hint.analyze(EXE, "kernel32", "FunctionThatDoesNotExistXYZ")
    assert h.call_sites == 0 and h.preferred_strategy_first() is None


def test_hint_orders_candidates_but_never_adds_forbidden():
    # ordre : S d'abord si indiqué, sur une classe où S est autorisé
    order = []
    def ev(c):
        order.append(c.strategy); return {"passed": True, "false_success": False, "detail": ""}
    search_answer("f", "state-query", "BOOL", True, False, ev, first_strategy="S")
    assert order[0] == "S"
    # sur tampon de sortie, l'indice S ne doit PAS faire apparaître de candidat S
    order2 = []
    def ev2(c):
        order2.append(c.strategy); return {"passed": True, "false_success": False, "detail": ""}
    search_answer("g", "output-buffer", "BOOL", True, True, ev2, first_strategy="S")
    assert order2 == ["A"]
