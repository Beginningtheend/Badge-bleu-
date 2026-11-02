"""Tests du générateur/linter de capsules et des oracles d'effet."""
import tomllib
from pathlib import Path
from bdflab.capsule import build_capsule, lint_capsule
from bdflab import oracles


def _cap(**over):
    kw = dict(
        identity={"sha256": "a" * 64, "imphash": "b" * 32, "product": "X", "version": "1.0", "publisher": "p"},
        wine_version="11.0", polyre_range=">=0.4, <0.5",
        contracts=[{"kind": "dll-provide", "dll": "bdfpdf", "source": "catalogue:bdfpdf", "sha256": "c" * 64, "mode": "native"}],
        shims=[{"dll": "kernel32", "func": "Heap32First", "strategy": "A", "api_class": "output-buffer", "returns": 0, "last_error": 120}],
        scenarios=["s1"], results={"s1": "pass"}, runs=2, machines=1, status="experimental", synthetic=True)
    kw.update(over)
    return build_capsule(**kw)


def test_capsule_roundtrip_and_lint_ok():
    cap = _cap()
    obj = tomllib.loads(cap.dumps())
    assert obj["meta"]["status"] == "experimental"
    assert obj["runtime"]["wine"] == "11.0"
    lr = lint_capsule(obj)
    assert lr.ok, lr.errors


def test_capsule_lint_rejects_s_output_buffer():
    cap = _cap(shims=[{"dll": "kernel32", "func": "X", "strategy": "S", "api_class": "output-buffer",
                       "returns": 1, "last_error": None}])
    obj = tomllib.loads(cap.dumps())
    lr = lint_capsule(obj)
    assert not lr.ok


def test_capsule_requires_wine_version():
    cap = _cap()
    obj = tomllib.loads(cap.dumps())
    obj["runtime"].pop("wine")
    lr = lint_capsule(obj)
    assert not lr.ok and any("wine" in e.lower() for e in lr.errors)


def test_oracle_false_success(tmp_path):
    missing = tmp_path / "nope.txt"
    r = oracles.oracle_file_contains(missing, "x", announced_saved=True)
    assert r.passed is False and r.false_success is True


def test_oracle_file_changed(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("a")
    before = oracles.sha256(f)
    f.write_text("a-modifie")
    r = oracles.oracle_file_changed(f, before, announced_saved=True)
    assert r.passed is True and r.false_success is False


def test_capsule_carries_branch_hint():
    cap = _cap(shims=[{"dll": "shcore", "func": "IsAppCompatModeEnabled", "strategy": "A", "api_class": "state-query",
                       "returns": 0, "last_error": 120,
                       "hint": {"tested": True, "predicted_nonzero_nominal": True, "confidence": "moyenne",
                                "suggested_first_strategy": "S", "call_sites": 1}}])
    obj = tomllib.loads(cap.dumps())
    bh = obj["shim"][0]["branch_hint"]
    assert bh["predicted_nonzero_nominal"] is True and bh["suggested_first_strategy"] == "S"
    assert lint_capsule(obj).ok
