"""Unit tests for the two pure decision helpers in the observability recorders.

Both encode security-relevant behaviour that used to be wrong:

* ``tool_status`` — a target refused by the SSRF/scope guard was written to the
  audit table as ``success`` (``blocked`` was unmapped and the fallback was
  ``success``), destroying the only durable proof the guard fired.
* ``chain_step_matches`` — attack-chain steps were linked to findings by
  unbounded bidirectional substring match, so a step of ``"ssh"`` attached every
  finding whose title mentions ssh.

No Django and no DB: ``apps.observability.recorders`` imports its ORM
dependencies lazily precisely so these can be tested here.
"""
import sys
import types

import pytest

from apps.observability import recorders
from apps.observability.recorders import (
    _MIN_CHAIN_STEP_CHARS,
    _TOOL_STATUS,
    chain_step_matches,
    tool_status,
)

# Mirrors observability.models.ToolStatus (importing it would need Django).
_TOOL_STATUS_VALUES = {"running", "success", "error", "timeout", "unavailable", "blocked"}


# ── tool status mapping ────────────────────────────────────────────────────
def test_blocked_target_is_recorded_as_blocked():
    # The scope guard sets status="blocked" (redweaver_engine/tools/
    # crewai_adapter.py). It is neither a success nor a tool error.
    assert tool_status("blocked") == "blocked"


def test_known_aliases_still_collapse():
    assert tool_status("success") == "success"
    assert tool_status("completed") == "success"
    assert tool_status("ok") == "success"
    assert tool_status("failed") == "error"
    assert tool_status("error") == "error"
    assert tool_status("timeout") == "timeout"
    assert tool_status("unavailable") == "unavailable"
    assert tool_status("running") == "running"


@pytest.mark.parametrize("raw", ["quarantined", "partial", "", "  ", None, 0, [], object()])
def test_unrecognised_status_is_error_never_success(raw):
    # An audit row must never claim a tool succeeded on evidence we can't read.
    assert tool_status(raw) == "error"


def test_unrecognised_status_is_logged(caplog):
    with caplog.at_level("WARNING", logger="apps.observability.recorders"):
        tool_status("quarantined")
    assert "quarantined" in caplog.text


def test_status_matching_tolerates_case_and_padding():
    assert tool_status("  Blocked ") == "blocked"
    assert tool_status("SUCCESS") == "success"


def test_every_mapped_status_is_a_real_toolstatus_value():
    # A typo here would raise only at INSERT time, inside a swallowed exception.
    assert set(_TOOL_STATUS.values()) <= _TOOL_STATUS_VALUES


# ── attack-chain / finding linking ─────────────────────────────────────────
def _lower(value: str) -> str:
    """Stand-in for Finding._norm_title (Django-bound, so not importable here).

    It normalizes strictly less than the real one, which makes these assertions
    conservative: anything the floor rejects here it also rejects in production.
    """
    return (value or "").lower().strip()


def test_three_letter_step_no_longer_matches_everything():
    # The regression: "ssh" is a substring of every ssh finding's title.
    for title in (
        "Open SSH port 22 on scanme.nmap.org",
        "SSH weak ciphers enabled",
        "OpenSSH user enumeration",
    ):
        assert chain_step_matches("ssh", title, normalize=_lower) is False


@pytest.mark.parametrize("step", ["ssh", "xss", "sqli", "port 22", "rce"])
def test_bare_category_nouns_are_rejected(step):
    assert len(step) < _MIN_CHAIN_STEP_CHARS
    assert chain_step_matches(step, "Reflected XSS in the search parameter", normalize=_lower) is False


def test_short_title_cannot_be_swallowed_by_a_long_step():
    # The other direction of the old bidirectional match: a long step containing
    # a tiny title used to link it.
    assert chain_step_matches(
        "Chain the RCE with credential reuse to pivot inward", "RCE", normalize=_lower
    ) is False


def test_step_quoting_the_finding_title_links():
    assert chain_step_matches(
        "Exploit the SQL injection in the login form to dump users",
        "SQL injection in the login form",
        normalize=_lower,
    ) is True


def test_title_quoting_the_step_links():
    assert chain_step_matches(
        "unauthenticated admin panel",
        "Unauthenticated admin panel exposed at /admin",
        normalize=_lower,
    ) is True


def test_unrelated_step_and_title_do_not_link():
    assert chain_step_matches(
        "Brute-force the exposed SSH service",
        "Reflected XSS in the search parameter",
        normalize=_lower,
    ) is False


@pytest.mark.parametrize("step,title", [(None, "Some finding title"), ("Some chain step", None), (None, None)])
def test_missing_text_never_links(step, title):
    assert chain_step_matches(step, title, normalize=_lower) is False


def test_default_normalizer_delegates_to_finding_norm_title(monkeypatch):
    """Chain links must use the same normalizer as finding dedup."""
    seen = []

    class _Finding:
        @staticmethod
        def _norm_title(value):
            seen.append(value)
            return (value or "").lower()

    stub = types.ModuleType("apps.findings.models")
    stub.Finding = _Finding
    monkeypatch.setitem(sys.modules, "apps.findings.models", stub)

    assert recorders._norm_title("Open Redirect On /go") == "open redirect on /go"
    assert seen == ["Open Redirect On /go"]

    # …and it is the default the predicate reaches for when none is injected.
    seen.clear()
    assert chain_step_matches("open redirect on /go", "Open Redirect On /go") is True
    assert seen
