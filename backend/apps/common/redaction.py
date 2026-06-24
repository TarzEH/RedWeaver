"""Redact secrets (API keys, tokens) from text before it is persisted or shown.

Provider error bodies echo back credential material. An OpenAI 401, for example,
includes a partial API key (``sk-proj-****…llsA``); that text lands in
``Run.error_message`` and is rendered in the UI, leaking key material into the
database and the browser. ``scrub_secrets`` masks the common token shapes (including
the asterisk-masked form providers return) while keeping the message diagnostic.
"""
from __future__ import annotations

import re

# (pattern, replacement) — most specific first. Token char classes include ``*``
# so the asterisk-masked form providers return (``sk-proj-****…llsA``) is caught too.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-proj-[A-Za-z0-9_*\-]{6,}"), "sk-proj-***REDACTED***"),
    (re.compile(r"sk-ant-[A-Za-z0-9_*\-]{6,}"), "sk-ant-***REDACTED***"),
    (re.compile(r"sk-[A-Za-z0-9_*\-]{12,}"), "sk-***REDACTED***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***REDACTED***"),
    (re.compile(r"ghp_[A-Za-z0-9]{16,}"), "ghp_***REDACTED***"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{20,}"), "AIza***REDACTED***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{8,}"), "xox-***REDACTED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***REDACTED***"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{12,}"), "Bearer ***REDACTED***"),
]


def scrub_secrets(text: str | None) -> str:
    """Return ``text`` with API keys / tokens masked. Empty string for falsy input."""
    if not text:
        return ""
    out = str(text)
    for pattern, replacement in _PATTERNS:
        out = pattern.sub(replacement, out)
    return out
