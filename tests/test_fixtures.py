"""Tests du chargeur de fixtures 0.1/0.2 (règle du professeur appliquée ensuite par speculate)."""
import json
import pytest
from bdflab.fixtures import load_fixtures, fixture_for, norm_key, validate_entry
from bdflab.speculate import fixture_stability, candidate_answers


def test_example_file_loads_and_is_stable():
    fx = load_fixtures("fixtures/example-illustratif.json")
    e = fixture_for(fx, "SHCORE.dll", "IsAppCompatModeEnabled")
    assert e and e["returns"] == 1 and "ILLUSTRATIF" in e["source"]
    ok, why = fixture_stability(e)
    assert ok and "2 entrées" in why
    c, _ = candidate_answers("state-query", "BOOL", synthetic=True, has_output_pointer=False, fixture=e)
    assert c[0].strategy == "F"


def test_norm_key_and_validation():
    assert norm_key("KERNEL32.dll.Foo") == "kernel32.Foo" and norm_key("kernel32.Foo") == "kernel32.Foo"
    with pytest.raises(ValueError):
        norm_key("Foo")
    assert validate_entry("a.B", {"returns": 1}) == []
    assert validate_entry("a.B", {"observations": [{"input": "x"}]})
    assert validate_entry("a.B", {"returns": "1"})


def test_bad_schema_and_bad_entry_are_refused(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"schema": "autre", "entries": {}}))
    with pytest.raises(ValueError):
        load_fixtures(p)
    p.write_text(json.dumps({"schema": "bdflab-fixtures/0.2", "source": "s", "entries": {"a.B": {"returns": "oui"}}}))
    with pytest.raises(ValueError):
        load_fixtures(p)


def test_varying_observations_are_not_a_rule(tmp_path):
    p = tmp_path / "f.json"
    p.write_text(json.dumps({"schema": "bdflab-fixtures/0.2", "source": "vm", "entries": {
        "x.GetMode": {"observations": [{"input": "doc A", "returns": 1}, {"input": "doc B", "returns": 2}]}}}))
    e = fixture_for(load_fixtures(p), "x", "GetMode")
    ok, why = fixture_stability(e)
    assert not ok and "fonderie" in why
