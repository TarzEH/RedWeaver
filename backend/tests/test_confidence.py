"""Unit tests for confidence scoring and its calibration.

The refactor from inline magic numbers to named weights must be behaviour-
preserving: the first block pins the exact scores the hand-tuned version
produced, so a future weight change is a deliberate act and not a silent drift.
"""
import json

import pytest

from apps.observability.calibration import (
    NotEnoughData,
    brier_score,
    feature_support,
    fit_weights,
)
from apps.observability.confidence import (
    DEFAULT_WEIGHTS,
    active_weights,
    derive_confidence,
    extract_features,
)


@pytest.fixture(autouse=True)
def _clean_weight_env(monkeypatch):
    """A weight override in the ambient environment would skew every assertion."""
    monkeypatch.delenv("CONFIDENCE_WEIGHTS", raising=False)


# ── behaviour preserved from the hand-tuned version ────────────────────────
def test_bare_finding_scores_the_neutral_prior():
    assert derive_confidence({}) == 0.4


def test_kev_and_proven_exploitability_stack():
    # 0.4 prior + 0.25 KEV + 0.25 proven = 0.9
    assert derive_confidence({"cisa_kev": True, "exploitability": "proven"}) == 0.9


def test_cvss_buckets_are_mutually_exclusive():
    assert derive_confidence({"cvss_score": 9.8}) == pytest.approx(0.55)
    assert derive_confidence({"cvss_score": 7.5}) == pytest.approx(0.5)
    assert derive_confidence({"cvss_score": 3.0}) == pytest.approx(0.45)
    assert derive_confidence({"cvss_score": 0}) == pytest.approx(0.4)


def test_epss_buckets_are_mutually_exclusive():
    assert derive_confidence({"epss_score": 0.7}) == pytest.approx(0.5)
    assert derive_confidence({"epss_score": 0.2}) == pytest.approx(0.45)
    assert derive_confidence({"epss_score": 0.01}) == pytest.approx(0.4)


def test_unlikely_exploitability_subtracts():
    assert derive_confidence({"exploitability": "unlikely"}) == pytest.approx(0.3)


def test_evidence_and_cve_add_corroboration():
    assert derive_confidence({"evidence": "nmap: 22/tcp open"}) == pytest.approx(0.5)
    assert derive_confidence({"evidence": "   "}) == pytest.approx(0.4)
    assert derive_confidence({"cve_ids": ["CVE-2021-1234"]}) == pytest.approx(0.45)


def test_score_is_clamped_to_unit_range():
    everything = {
        "cisa_kev": True, "exploitability": "proven", "cvss_score": 10.0,
        "cve_ids": ["CVE-2021-1"], "evidence": "proof", "epss_score": 0.9,
    }
    assert derive_confidence(everything) == 1.0


def test_booleans_are_not_treated_as_numeric_scores():
    # bool is a subclass of int; True must not be read as a CVSS of 1.0.
    features = extract_features({"cvss_score": True, "epss_score": True})
    assert features["cvss_any"] == 0.0
    assert features["epss_medium"] == 0.0


# ── weights are configurable ───────────────────────────────────────────────
def test_env_override_merges_over_defaults(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHTS", json.dumps({"bias": 0.9}))
    weights = active_weights()
    assert weights["bias"] == 0.9
    assert weights["cisa_kev"] == DEFAULT_WEIGHTS["cisa_kev"]
    assert derive_confidence({}) == 0.9


def test_unknown_or_malformed_overrides_are_ignored(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHTS", json.dumps({"not_a_feature": 1.0, "bias": "high"}))
    assert active_weights() == DEFAULT_WEIGHTS

    monkeypatch.setenv("CONFIDENCE_WEIGHTS", "{oops")
    assert active_weights() == DEFAULT_WEIGHTS


def test_explicit_weights_argument_wins_over_env(monkeypatch):
    monkeypatch.setenv("CONFIDENCE_WEIGHTS", json.dumps({"bias": 0.9}))
    assert derive_confidence({}, weights={**DEFAULT_WEIGHTS, "bias": 0.1}) == 0.1


# ── calibration ────────────────────────────────────────────────────────────
def labelled_set(n=20):
    """Findings where evidence perfectly predicts the label, KEV predicts nothing."""
    samples = []
    for i in range(n):
        samples.append((extract_features({"evidence": "proof", "cisa_kev": i % 2 == 0}), 1))
        samples.append((extract_features({"evidence": "", "cisa_kev": i % 2 == 0}), 0))
    return samples


def test_calibration_refuses_a_tiny_labelled_set():
    with pytest.raises(NotEnoughData, match="worse than the default"):
        fit_weights(labelled_set(n=3))


def test_calibration_requires_both_classes():
    positives = [(extract_features({"evidence": "x"}), 1) for _ in range(50)]
    with pytest.raises(NotEnoughData):
        fit_weights(positives)


def test_calibration_improves_the_brier_score():
    samples = labelled_set()
    result = fit_weights(samples)
    assert result.fitted_brier <= result.baseline_brier
    assert result.improvement > 0
    assert brier_score(samples, result.weights) == result.fitted_brier


def test_calibration_learns_the_predictive_signal():
    # Evidence separates the classes here, so its weight should grow.
    result = fit_weights(labelled_set())
    assert result.weights["has_evidence"] > DEFAULT_WEIGHTS["has_evidence"]


def test_calibration_reports_class_counts():
    result = fit_weights(labelled_set(n=20))
    assert result.samples == 40
    assert result.positives == 20
    assert result.negatives == 20


def test_feature_support_flags_thinly_evidenced_weights():
    samples = labelled_set(n=20)
    support = feature_support(samples)
    assert support["bias"] == 40
    assert support["has_evidence"] == 20
    # Nothing in this set carries a CVSS score, so its weight is unsupported.
    assert support["cvss_critical"] == 0


def test_fitted_weights_stay_within_bounds():
    result = fit_weights(labelled_set())
    for name, value in result.weights.items():
        assert -0.5 <= value <= 0.6, f"{name} escaped its bounds"


def test_brier_of_an_empty_set_is_zero():
    assert brier_score([], DEFAULT_WEIGHTS) == 0.0
