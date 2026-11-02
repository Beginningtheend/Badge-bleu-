"""Tests du communs de capsules adressé par contenu."""
from pathlib import Path
from bdflab.capsule import build_capsule
from bdflab.commons import CapsuleCommons


def _mkcap(tmp, sha, imphash, name):
    cap = build_capsule(
        identity={"sha256": sha, "imphash": imphash, "product": "X", "version": "1.0", "publisher": "p"},
        wine_version="11.0", polyre_range=">=0.4, <0.5", contracts=[],
        shims=[{"dll": "kernel32", "func": "Heap32First", "strategy": "A", "api_class": "output-buffer", "returns": 0, "last_error": 120}],
        scenarios=["s1"], results={"s1": "pass"}, runs=2, machines=1, status="experimental", synthetic=True)
    p = tmp / name
    cap.dump(p)
    return p


def test_commons_exact_and_degraded_and_miss(tmp_path):
    commons = CapsuleCommons(tmp_path / "commons")
    cap = _mkcap(tmp_path, "a" * 64, "b" * 32, "x.capsule.toml")
    commons.put(cap)
    # exact par sha256
    assert commons.get("a" * 64, "b" * 32).match == "exact"
    # dégradé : même imphash, sha différent
    assert commons.get("c" * 64, "b" * 32).match == "degraded"
    # absent
    assert commons.get("d" * 64, "e" * 32).match == "none"


def test_commons_persists_index(tmp_path):
    root = tmp_path / "commons"
    c1 = CapsuleCommons(root)
    c1.put(_mkcap(tmp_path, "f" * 64, "0" * 32, "y.capsule.toml"))
    # recharger depuis le disque
    c2 = CapsuleCommons(root)
    assert c2.get("f" * 64).match == "exact"
