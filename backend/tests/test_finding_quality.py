"""Unit tests for finding-quality guards: secret redaction, noise down-ranking,
and corrected ATT&CK mapping (all pure functions, no DB)."""
from apps.common.redaction import scrub_secrets
from apps.findings.attack_map import techniques_for
from apps.findings.noise import downgrade_expected_noise


# ── secret redaction ───────────────────────────────────────────────────────
def test_scrub_masks_openai_key_fragment():
    # The asterisk-masked form an OpenAI 401 actually returns.
    raw = "Incorrect API key provided: sk-proj-************************llsA. Find it at..."
    out = scrub_secrets(raw)
    assert "llsA" not in out
    assert "REDACTED" in out


def test_scrub_masks_common_token_shapes():
    assert "ghp_" in scrub_secrets("token ghp_0123456789abcdefABCDEF leaked") and \
        "0123456789abcdefABCDEF" not in scrub_secrets("token ghp_0123456789abcdefABCDEF leaked")
    assert "REDACTED" in scrub_secrets("Authorization: Bearer abcdef0123456789ghij")


def test_scrub_leaves_clean_text_untouched():
    msg = "Hunt exceeded its time limit (900s)"
    assert scrub_secrets(msg) == msg
    assert scrub_secrets("") == ""
    assert scrub_secrets(None) == ""


# ── noise down-ranking ─────────────────────────────────────────────────────
def test_open_web_port_downgraded_to_info():
    out = downgrade_expected_noise(
        {"title": "Open TCP port 443 on www.example.com", "severity": "low", "cve_ids": []}
    )
    assert out["severity"] == "info"
    assert "informational" in out["description"].lower()


def test_open_port_with_cve_is_kept():
    data = {"title": "Open TCP port 443", "severity": "low", "cve_ids": ["CVE-2010-1802"]}
    assert downgrade_expected_noise(data)["severity"] == "low"


def test_open_port_with_vuln_signal_is_kept():
    data = {"title": "Open port 443 with self-signed certificate", "severity": "low", "cve_ids": []}
    assert downgrade_expected_noise(data)["severity"] == "low"


def test_unexpected_port_is_kept():
    data = {"title": "Open TCP port 3389 (RDP)", "severity": "low", "cve_ids": []}
    assert downgrade_expected_noise(data)["severity"] == "low"


def test_high_severity_never_downgraded():
    data = {"title": "Open TCP port 443", "severity": "high", "cve_ids": []}
    assert downgrade_expected_noise(data)["severity"] == "high"


def test_real_finding_untouched():
    data = {"title": "SQL injection in login form", "severity": "high", "cve_ids": []}
    assert downgrade_expected_noise(data) is data


# ── corrected ATT&CK mapping ───────────────────────────────────────────────
def test_ssl_cve_maps_to_aitm_not_client_execution():
    ids = [t["id"] for t in techniques_for(
        {"title": "CVE-2010-1802: SSL Spoofing Vulnerability", "description": ""}
    )]
    assert "T1557" in ids          # Adversary-in-the-Middle
    assert "T1190" in ids          # Exploit Public-Facing Application (generic CVE)
    assert "T1203" not in ids      # no longer mis-mapped to client execution


def test_outdated_component_maps_to_public_facing():
    ids = [t["id"] for t in techniques_for(
        {"title": "Outdated nginx version detected", "description": ""}
    )]
    assert "T1190" in ids
