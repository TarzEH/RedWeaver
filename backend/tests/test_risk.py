"""Unit tests for the SSVC-style risk prioritization engine (no DB)."""
from apps.findings.risk import compute_risk


def test_kev_high_is_act():
    r = compute_risk(cvss=9.8, epss=0.94, cisa_kev=True, exploitability="proven", severity="critical")
    assert r["decision"] == "act"
    assert r["risk_score"] > 90
    assert r["weaponized"] is True


def test_low_info_is_track():
    r = compute_risk(cvss=None, epss=None, cisa_kev=False, exploitability="unknown", severity="low")
    assert r["decision"] == "track"
    assert r["risk_score"] < 30


def test_high_cvss_no_exploit_is_attend():
    r = compute_risk(cvss=8.1, epss=0.02, cisa_kev=False, exploitability="unknown", severity="high")
    assert r["decision"] == "attend"


def test_score_is_bounded():
    r = compute_risk(cvss=10, epss=1.0, cisa_kev=True, exploitability="proven", severity="critical")
    assert 0 <= r["risk_score"] <= 100


def test_epss_increases_risk():
    low = compute_risk(cvss=5, epss=0.0, cisa_kev=False, exploitability="unknown", severity="medium")
    high = compute_risk(cvss=5, epss=0.9, cisa_kev=False, exploitability="unknown", severity="medium")
    assert high["risk_score"] > low["risk_score"]
