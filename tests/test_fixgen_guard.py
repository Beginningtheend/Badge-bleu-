"""Garde d'architecture : une application 32 bits est refusée explicitement (v0.1 = ABI Win64 seulement)."""
from types import SimpleNamespace
from pathlib import Path
import pytest
from bdflab.fixgen import FixPlan, build_fix


def test_i386_is_refused_before_any_build(tmp_path):
    plan = FixPlan(identity={}, problems=[], declarative=[], shims=[], rejected=[], notes=[])
    with pytest.raises(ValueError, match="x86-64 seulement"):
        build_fix(plan, Path("absent.exe"), tmp_path / "fix", SimpleNamespace(machine="i386"))
    assert not (tmp_path / "fix").exists()
