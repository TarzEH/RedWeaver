"""Unit tests for the SSRF scope guard, confidence, and cost (no DB)."""
from apps.hunts.costs import estimate_cost_usd
from apps.observability.confidence import derive_confidence
from redweaver_engine.tools.scope import check_target


def test_scope_blocks_metadata():
    ok, reason = check_target("http://169.254.169.254/latest/meta-data/")
    assert ok is False and "metadata" in reason.lower()


def test_scope_allows_public():
    assert check_target("scanme.nmap.org")[0] is True
    assert check_target("http://testaspnet.vulnweb.com/login.aspx")[0] is True


def test_scope_allows_non_network_inputs():
    # search queries / CVE ids must pass through (they don't resolve to a blocked IP)
    assert check_target("linux privilege escalation")[0] is True
    assert check_target("CVE-2021-44224")[0] is True


def test_confidence_uses_kev_and_exploitability():
    base = derive_confidence({"severity": "high"})
    strong = derive_confidence({"cisa_kev": True, "exploitability": "proven", "cvss_score": 9.5,
                                "cve_ids": ["CVE-1"], "evidence": "x", "epss_score": 0.9})
    assert strong > base
    assert 0.0 <= strong <= 1.0


def test_cost_estimation_scales_with_tokens():
    cheap = estimate_cost_usd("gpt-4o-mini", 1000, 1000)
    pricey = estimate_cost_usd("claude-opus-4", 1000, 1000)
    assert pricey > cheap >= 0
