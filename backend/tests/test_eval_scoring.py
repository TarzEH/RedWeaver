"""Unit tests for the hunt evaluation harness (golden-set scoring)."""
import pytest

from redweaver_engine.evaluation.scoring import (
    GoldenSetError,
    compare,
    parse_golden,
    score_findings,
)

GOLDEN = parse_golden({
    "name": "demo",
    "target": "http://demo.local",
    "expected": [
        {"id": "sqli", "title_any": ["sql injection"], "min_severity": "high"},
        {"id": "xss", "title_any": ["xss", "cross-site scripting"]},
        {"id": "admin-panel", "title_any": ["admin"], "url_any": ["/admin"]},
    ],
    "forbidden": [
        {"id": "not-wordpress", "title_any": ["wordpress"]},
    ],
})


def finding(title, severity="high", url="", description=""):
    return {
        "title": title, "severity": severity,
        "affected_url": url, "description": description,
    }


# ── golden set parsing ─────────────────────────────────────────────────────
def test_golden_requires_at_least_one_expectation():
    with pytest.raises(GoldenSetError):
        parse_golden({"name": "empty", "expected": []})


def test_rule_without_any_matcher_is_rejected():
    # A rule with no title_any/url_any would match every finding and silently
    # report perfect recall.
    with pytest.raises(GoldenSetError, match="match every finding"):
        parse_golden({"expected": [{"id": "catch-all", "min_severity": "low"}]})


def test_expected_must_be_a_list():
    with pytest.raises(GoldenSetError):
        parse_golden({"expected": "sqli"})


# ── matching ───────────────────────────────────────────────────────────────
def test_title_match_is_case_insensitive_and_substring():
    result = score_findings([finding("Blind SQL Injection in /products")], GOLDEN)
    assert result.matched_expectations == ["sqli"]


def test_description_is_searched_too():
    result = score_findings(
        [finding("Parameter tampering", description="leads to XSS in the search box")],
        GOLDEN,
    )
    assert "xss" in result.matched_expectations


def test_min_severity_gates_the_match():
    # Right vulnerability, under-rated severity -> not credited.
    low = score_findings([finding("SQL Injection", severity="low")], GOLDEN)
    assert low.matched_expectations == []
    assert low.unscored == 1

    high = score_findings([finding("SQL Injection", severity="critical")], GOLDEN)
    assert high.matched_expectations == ["sqli"]


def test_all_declared_constraints_must_hold():
    # admin-panel needs both the title and the URL.
    assert score_findings([finding("Admin login page", url="/login")], GOLDEN).unscored == 1
    assert score_findings(
        [finding("Admin login page", url="/admin/login")], GOLDEN
    ).matched_expectations == ["admin-panel"]


# ── the three outcomes ─────────────────────────────────────────────────────
def test_findings_split_into_true_false_and_unscored():
    result = score_findings([
        finding("SQL Injection in /products", severity="critical"),   # TP
        finding("WordPress 4.2 detected"),                            # FP (forbidden)
        finding("Server header discloses nginx version"),             # unscored
    ], GOLDEN)

    assert result.true_positives == 1
    assert result.false_positives == 1
    assert result.unscored == 1
    assert result.false_positive_titles == ["WordPress 4.2 detected"]


def test_unscored_findings_never_count_as_false_positives():
    # "The answer key is silent" must not be scored as "wrong".
    result = score_findings([finding(f"Unrelated observation {i}") for i in range(9)], GOLDEN)
    assert result.false_positives == 0
    assert result.unscored == 9
    assert result.noise_ratio == 1.0


# ── metrics ────────────────────────────────────────────────────────────────
def test_recall_counts_expectations_not_findings():
    # Two findings matching the same expectation is still one of three found.
    result = score_findings([
        finding("SQL Injection in /products", severity="critical"),
        finding("SQL Injection in /artists", severity="critical"),
    ], GOLDEN)
    assert result.true_positives == 2
    assert result.recall == pytest.approx(1 / 3, abs=1e-4)
    assert result.missed_expectations == ["admin-panel", "xss"]


def test_precision_is_none_when_nothing_was_scorable():
    # An honest "unknown" — not a free 100%.
    result = score_findings([finding("Totally unrelated")], GOLDEN)
    assert result.precision is None
    assert result.f1 is None


def test_precision_and_f1_over_scored_findings():
    result = score_findings([
        finding("SQL Injection", severity="critical"),
        finding("Cross-site scripting in search"),
        finding("WordPress detected"),
    ], GOLDEN)
    assert result.precision == pytest.approx(2 / 3, abs=1e-4)
    assert result.recall == pytest.approx(2 / 3, abs=1e-4)
    assert result.f1 == pytest.approx(2 / 3, abs=1e-4)


def test_empty_run_scores_zero_recall_without_crashing():
    result = score_findings([], GOLDEN)
    assert result.recall == 0.0
    assert result.precision is None
    assert result.noise_ratio == 0.0
    assert len(result.missed_expectations) == 3


def test_non_mapping_findings_are_skipped():
    result = score_findings(
        [None, "a string", finding("SQL Injection", severity="high")], GOLDEN
    )
    assert result.total_findings == 1
    assert result.true_positives == 1


# ── baseline comparison ────────────────────────────────────────────────────
def test_compare_reports_deltas_and_regressions():
    before = score_findings([
        finding("SQL Injection", severity="critical"),
        finding("XSS in search"),
    ], GOLDEN).to_dict()
    after = score_findings([finding("XSS in search")], GOLDEN).to_dict()

    diff = compare(before, after)
    assert diff["recall"]["delta"] < 0
    assert diff["newly_missed"] == ["sqli"]
    assert diff["newly_found"] == []


def test_compare_skips_deltas_for_missing_metrics():
    diff = compare({"recall": 0.5}, {"recall": None})
    assert diff["recall"]["delta"] is None
