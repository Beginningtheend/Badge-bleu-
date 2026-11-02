"""Tests de la fonderie : acceptation uniquement si tous les oracles passent sans faux succès."""
from pathlib import Path
from bdflab.foundry import Proposal, verify_proposal, FoundryVerdict
from bdflab.oracles import OracleResult
from bdflab import foundry


def _fake_build(monkeypatch, ok=True):
    class BF:  # bundle factice
        patched_exe = "x"; generated_dlls = []
    def fake_build_fix(plan, exe, out, surface, catalogue_dir=None):
        if not ok:
            raise RuntimeError("compile error")
        return BF()
    monkeypatch.setattr(foundry, "build_fix", fake_build_fix)


def test_accepts_when_all_oracles_pass(monkeypatch, tmp_path):
    _fake_build(monkeypatch)
    prop = Proposal("kernel32", "F", "BOOL", "output-buffer", "human", "int bdf_impl_F(void){return 1;}")
    v = verify_proposal(prop, [], Path("exe"), None, tmp_path,
                        lambda d, bf: ([OracleResult("a", True, ""), OracleResult("b", True, "")], True))
    assert v.accepted and not v.false_success


def test_rejects_false_success(monkeypatch, tmp_path):
    _fake_build(monkeypatch)
    prop = Proposal("kernel32", "F", "BOOL", "output-buffer", "offline-model", "int bdf_impl_F(void){return 1;}")
    v = verify_proposal(prop, [], Path("exe"), None, tmp_path,
                        lambda d, bf: ([OracleResult("ts", False, "0000-00-00", false_success=True)], True))
    assert not v.accepted and v.false_success and "faux succès" in v.note


def test_rejects_when_compile_fails(monkeypatch, tmp_path):
    _fake_build(monkeypatch, ok=False)
    prop = Proposal("kernel32", "F", "BOOL", "output-buffer", "offline-model", "garbage(")
    v = verify_proposal(prop, [], Path("exe"), None, tmp_path, lambda d, bf: ([], False))
    assert not v.accepted and "compile" in v.detail.lower()
