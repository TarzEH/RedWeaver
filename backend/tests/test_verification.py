"""Unit tests for the adversarial verification pass (pure scoring logic).

`apply_verdicts` needs a database and is exercised in integration; everything
here is the decision logic it delegates to.
"""
import pytest

from apps.findings.verification import (
    blend_confidence,
    normalize_verdict,
    rank_for_verification,
    status_for_verdict,
)
from redweaver_engine.crews.verify import findings_payload


# ── verdict normalization ──────────────────────────────────────────────────
def test_known_verdicts_pass_through():
    assert normalize_verdict("confirmed") == "confirmed"
    assert normalize_verdict("  REFUTED ") == "refuted"


def test_synonyms_map_onto_known_verdicts():
    assert normalize_verdict("false positive") == "refuted"
    assert normalize_verdict("true_positive") == "confirmed"


def test_anything_unrecognized_is_uncertain_not_a_guess():
    for value in ("maybe", "", None, "probably real"):
        assert normalize_verdict(value) == "uncertain"


# ── status decisions ───────────────────────────────────────────────────────
def test_confident_refutation_marks_false_positive():
    assert status_for_verdict("refuted", 0.9) == "false_positive"


def test_confident_confirmation_marks_confirmed():
    assert status_for_verdict("confirmed", 0.95) == "confirmed"


def test_weak_verdict_changes_nothing():
    # Below threshold the verifier does not get to move triage state.
    assert status_for_verdict("refuted", 0.3) is None
    assert status_for_verdict("confirmed", 0.5) is None


def test_uncertain_never_changes_status_however_confident():
    assert status_for_verdict("uncertain", 1.0) is None


def test_malformed_confidence_is_treated_as_no_confidence():
    assert status_for_verdict("refuted", None) is None
    assert status_for_verdict("refuted", "very sure") is None


def test_out_of_range_confidence_is_clamped():
    assert status_for_verdict("refuted", 5.0) == "false_positive"
    assert status_for_verdict("refuted", -3.0) is None


# ── confidence blending ────────────────────────────────────────────────────
def test_refutation_pulls_confidence_down():
    assert blend_confidence(0.8, "refuted", 1.0) < 0.8


def test_confirmation_pushes_confidence_up():
    assert blend_confidence(0.4, "confirmed", 1.0) > 0.4


def test_uncertain_verdict_leaves_the_prior_untouched():
    assert blend_confidence(0.62, "uncertain", 0.9) == 0.62


def test_verdict_strength_scales_the_movement():
    weak = blend_confidence(0.8, "refuted", 0.2)
    strong = blend_confidence(0.8, "refuted", 1.0)
    assert strong < weak < 0.8


def test_missing_prior_starts_from_neutral():
    assert blend_confidence(None, "uncertain", 0.5) == 0.5


def test_result_stays_within_range():
    for prior in (0.0, 0.5, 1.0):
        for verdict in ("confirmed", "refuted", "uncertain"):
            value = blend_confidence(prior, verdict, 1.0)
            assert 0.0 <= value <= 1.0


# ── candidate selection ────────────────────────────────────────────────────
def test_info_findings_are_not_worth_verifying():
    items = [{"severity": "info", "title": "port open"}, {"severity": "high", "title": "sqli"}]
    picked = rank_for_verification(items, limit=10)
    assert [p["title"] for p in picked] == ["sqli"]


def test_selection_is_severity_ordered_and_capped():
    items = [
        {"severity": "low", "title": "low"},
        {"severity": "critical", "title": "crit"},
        {"severity": "medium", "title": "med"},
    ]
    picked = rank_for_verification(items, limit=2)
    assert [p["title"] for p in picked] == ["crit", "med"]


def test_limit_of_zero_selects_nothing():
    assert rank_for_verification([{"severity": "critical"}], limit=0) == []


def test_selection_accepts_objects_not_only_dicts():
    class Row:
        def __init__(self, severity):
            self.severity = severity

    picked = rank_for_verification([Row("info"), Row("critical")], limit=5)
    assert len(picked) == 1
    assert picked[0].severity == "critical"


# ── what the verifier is allowed to see ────────────────────────────────────
def test_payload_keeps_evidence_and_drops_persuasion():
    payload = findings_payload([{
        "title": "SQL injection",
        "evidence": "sqlmap: parameter id is injectable",
        "severity": "critical",
        "remediation": "use prepared statements",
        "affected_url": "http://x/products?id=1",
    }])
    assert payload[0]["evidence"].startswith("sqlmap")
    assert payload[0]["affected_url"]
    # Severity and remediation prose would bias the judgement, not evidence it.
    assert "severity" not in payload[0]
    assert "remediation" not in payload[0]


def test_payload_skips_untitled_and_non_dict_entries():
    assert findings_payload([{"evidence": "x"}, None, "string"]) == []


def test_payload_omits_empty_fields():
    payload = findings_payload([{"title": "t", "evidence": "", "description": None}])
    assert payload == [{"title": "t"}]


@pytest.mark.parametrize("verdict", ["confirmed", "refuted", "uncertain"])
def test_blend_is_deterministic(verdict):
    assert blend_confidence(0.5, verdict, 0.7) == blend_confidence(0.5, verdict, 0.7)
