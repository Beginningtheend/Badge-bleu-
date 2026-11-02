"""Tests de la classification A/B/C/D et de la table de sûreté."""
import pytest
from bdflab.classify import classify_problem, classify_api
from bdflab.safety import evaluate, lint_shim, SAFETY_TABLE


@pytest.mark.parametrize("dll,func,status,proto,expect_class,expect_api", [
    ("wintrust", "WinVerifyTrust", "stub", {"ret": "LONG", "params": []}, "D", "security"),
    ("crypt32", "CryptDecodeMessage", "stub", {"ret": "BOOL", "params": []}, "D", "security"),
    ("kernel32", "WaitForSingleObject", "stub", {"ret": "DWORD", "params": [["HANDLE", ""], ["DWORD", ""]]}, "C", "sync-time"),
    ("mfc140u", "#1", "dll-missing", None, "A", "unknown"),
    ("msvcp140", "#2", "dll-missing", None, "A", "unknown"),
    ("kernel32", "Heap32First", "stub", {"ret": "BOOL", "params": [["LPHEAPENTRY32", ""], ["DWORD", ""], ["ULONG_PTR", ""]]}, "B", "output-buffer"),
    ("kernel32", "IsProcessRestricted", "stub", {"ret": "BOOL", "params": []}, "B", "state-query"),
])
def test_classify(dll, func, status, proto, expect_class, expect_api):
    p = classify_problem(dll, func, status, proto, ["ev"])
    assert p.contract_class == expect_class, (func, p.contract_class)
    assert p.api_class == expect_api, (func, p.api_class)


def test_security_never_fixable():
    p = classify_problem("secur32", "LsaRegisterLogonProcess", "stub", {"ret": "NTSTATUS", "params": []}, [])
    assert p.contract_class == "D"
    assert p.fixable_v01 is False


def test_safety_table_s_forbidden_on_output_buffer():
    v = evaluate("B", "output-buffer", has_output_pointer=True, synthetic=True)
    assert v.a_allowed is True
    assert v.s_allowed_lab is False


def test_safety_s_allowed_state_query_no_buffer():
    v = evaluate("B", "state-query", has_output_pointer=False, synthetic=True)
    assert v.s_allowed_lab is True
    # mais interdit si tampon de sortie
    v2 = evaluate("B", "state-query", has_output_pointer=True, synthetic=True)
    assert v2.s_allowed_lab is False


def test_safety_production_never_s():
    v = evaluate("B", "state-query", has_output_pointer=False, synthetic=True)
    assert v.s_allowed_production is False  # une capsule expérimentale ne permet jamais S en prod


def test_lint_rejects_s_on_persistent_nonsynthetic():
    issues = lint_shim("B", "persistent-mutation", "S", False, synthetic=False, returns=1, last_error=None, status="experimental")
    assert any(i.level == "error" for i in issues)


def test_lint_rejects_class_D():
    issues = lint_shim("D", "security", "A", False, True, 0, 120, "stub")
    assert any(i.code == "class-D-forbidden" for i in issues)


def test_lint_accepts_A_declared_absence():
    issues = lint_shim("B", "output-buffer", "A", True, True, 0, 120, "export-absent")
    assert not [i for i in issues if i.level == "error"]
