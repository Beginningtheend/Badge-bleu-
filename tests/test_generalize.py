"""Tests de la généralisation : verdict en trois valeurs, jamais présumé ; garde-fous ; oracle fort."""
import datetime as dt

from bdflab.generalize import (HeldOutRecord, generalization_verdict, overlap, constant_output_suspect,
                               capsule_section, annotate_capsule, family_of)
from bdflab.oracles import oracle_timestamp_fresh, oracle_timestamp_plausible
from bdflab.capsule import lint_capsule, load_capsule, build_capsule


def rec(action, passed=True, fs=False, stamp=None):
    return HeldOutRecord(action, passed, fs, 0, [("o", passed)], {"stamp": stamp})


def test_generalizes_with_new_inputs_and_new_scenarios():
    v = generalization_verdict(["edit:reference"], [rec("edit:a", stamp="1"), rec("edit:b", stamp="2"),
                                                    rec("stats:x"), rec("export-pdf:y")], input_dependent_key="stamp")
    assert v["verdict"] == "generalizes" and v["scope"] == "new-inputs-and-new-scenarios"
    assert v["new_families"] == ["export-pdf", "stats"] and not v["constant_output_suspect"]


def test_new_inputs_only_scope():
    v = generalization_verdict(["edit:reference"], [rec("edit:a", stamp="1"), rec("edit:b", stamp="2"),
                                                    rec("edit:c", stamp="3")], input_dependent_key="stamp")
    assert v["verdict"] == "generalizes" and v["scope"] == "new-inputs" and v["new_families"] == []


def test_false_success_means_does_not_generalize():
    v = generalization_verdict(["edit:reference"], [rec("edit:a"), rec("edit:b", passed=False, fs=True), rec("edit:c")])
    assert v["verdict"] == "does-not-generalize" and "faux succès" in v["reasons"][0]


def test_plain_failure_means_does_not_generalize():
    v = generalization_verdict(["edit:reference"], [rec("edit:a"), rec("edit:b", passed=False), rec("edit:c")])
    assert v["verdict"] == "does-not-generalize" and "échec" in v["reasons"][0]


def test_replayed_constant_output_is_recitation_not_rule():
    # oracle faible satisfait partout, mais l'horodatage est identique sur toutes les actions : valeur rejouée
    recs = [rec("edit:a", stamp="2026-10-30 09:41:07"), rec("edit:b", stamp="2026-10-30 09:41:07"),
            rec("edit:c", stamp="2026-10-30 09:41:07")]
    v = generalization_verdict(["edit:reference"], recs, input_dependent_key="stamp")
    assert v["verdict"] == "does-not-generalize" and v["constant_output_suspect"] and "rejouée" in v["reasons"][0]
    # sans clé dépendante de l'entrée, le même jeu passe : le garde-fou doit être demandé explicitement
    assert generalization_verdict(["edit:reference"], recs)["verdict"] == "generalizes"


def test_too_few_actions_cannot_judge():
    v = generalization_verdict(["edit:reference"], [rec("edit:a"), rec("edit:b")])
    assert v["verdict"] == "cannot-judge" and "trop peu" in v["reasons"][0]
    assert generalization_verdict(["edit:reference"], [])["verdict"] == "cannot-judge"


def test_learning_actions_counted_as_held_out_cannot_judge():
    v = generalization_verdict(["edit:reference"], [rec("edit:reference"), rec("edit:a"), rec("edit:b")])
    assert v["verdict"] == "cannot-judge"
    assert overlap(["edit:reference"], ["edit:reference", "x"]) == ["edit:reference"]


def test_helpers():
    assert family_of("export-pdf:doc") == "export-pdf" and family_of("stats") == "stats"
    assert constant_output_suspect(["a", "a", None, "a"])
    assert not constant_output_suspect(["a", "b"]) and not constant_output_suspect(["a"])


def _doc(tmp_path, stamp):
    p = tmp_path / "d.txt"
    p.write_text(f"x\n# saved-at {stamp}\n")
    return p


def test_fresh_oracle_accepts_current_time_and_rejects_replayed_value(tmp_path):
    now = dt.datetime(2026, 11, 2, 10, 0, 0)
    ok = oracle_timestamp_fresh(_doc(tmp_path, "2026-11-02 10:03:20"), now)
    assert ok.passed and not ok.false_success
    stale = oracle_timestamp_fresh(_doc(tmp_path, "2026-10-30 09:41:07"), now)
    assert not stale.passed and stale.false_success and "PÉRIMÉ" in stale.detail
    # l'oracle FAIBLE laisse passer la même valeur rejouée : l'oracle doit être aussi fort que la propriété généralisée
    assert oracle_timestamp_plausible(_doc(tmp_path, "2026-10-30 09:41:07")).passed


def test_fresh_oracle_missing_footer_is_false_success_when_announced(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("no footer\n")
    r = oracle_timestamp_fresh(p, dt.datetime.now())
    assert not r.passed and r.false_success
    assert not oracle_timestamp_fresh(tmp_path / "absent.txt", dt.datetime.now(), announced_saved=False).false_success


def _capsule(tmp_path, status="experimental"):
    c = build_capsule({"sha256": "a" * 64, "imphash": "b" * 32}, "wine-11.0", ">=0", [],
                      [{"dll": "kernel32", "func": "Heap32First", "strategy": "A", "api_class": "output-buffer",
                        "returns": 0, "last_error": 120}],
                      ["edit"], {"edit": {"passed": True}}, 2, 1, status, True)
    p = tmp_path / "c.toml"
    c.dump(p)
    return p


def test_annotate_capsule_and_lint(tmp_path):
    p = _capsule(tmp_path)
    v = generalization_verdict(["edit:reference"], [rec("edit:a"), rec("edit:b"), rec("stats:x")])
    obj = annotate_capsule(p, capsule_section(v, "strong"))
    assert obj["generalization"]["verdict"] == "generalizes"
    text = p.read_text()
    assert text.startswith("# Capsule PolyRE") and "[generalization]" in text
    assert lint_capsule(load_capsule(p)).ok


def test_lint_rejects_validated_capsule_that_does_not_generalize(tmp_path):
    p = _capsule(tmp_path, status="validated")
    obj = load_capsule(p)
    obj["provenance"]["signature"] = "sig"   # sinon erreur « sans signature »
    bad = generalization_verdict(["edit:reference"], [rec("edit:a", passed=False, fs=True), rec("edit:b"), rec("edit:c")])
    obj["generalization"] = capsule_section(bad, "strong")
    lint = lint_capsule(obj)
    assert not lint.ok and any("généralisation" in e for e in lint.errors)
    obj["generalization"]["verdict"] = "bogus"
    assert any("verdict" in e for e in lint_capsule(obj).errors)


def test_lint_blocks_validated_capsule_without_generalization_or_two_runs(tmp_path):
    p = _capsule(tmp_path, status="validated")
    obj = load_capsule(p)
    obj["provenance"]["signature"] = "sig"
    lint = lint_capsule(obj)
    assert not lint.ok and any("généralisation" in e for e in lint.errors)
    obj["validation"]["runs"] = 1
    assert any("runs < 2" in e for e in lint_capsule(obj).errors)
    # en « experimental », les mêmes manques ne sont que des avertissements
    obj["meta"]["status"] = "experimental"
    assert lint_capsule(obj).ok
