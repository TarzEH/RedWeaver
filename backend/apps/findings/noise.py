"""Down-rank expected, non-actionable observations to informational severity.

The recon stage reports every open port as a "finding". A standard web service
port (80/443) that is simply *open*, with no associated CVE or vulnerability
signal, is expected — not a Low-severity issue. Ranking it Low inflates the
finding count and pollutes the severity breakdown, the OWASP/ATT&CK rollups and
the headline risk rating. This module recognizes that bare-observation shape and
downgrades it to ``info`` (kept, not dropped — the data stays, just ranked
truthfully).

Conservative by design: only a finding whose *title* is a bare open-port
observation, on an expected web port, with no CVE and no vulnerability keyword,
is touched. ``high``/``critical`` are never downgraded.
"""
from __future__ import annotations

import re

# Ports expected to be open on a typical web/HTTP target.
_EXPECTED_WEB_PORTS = {"80", "443", "8080", "8443"}

# A bare open-port observation in a title: "Open TCP port 443 …" or "… port 443 open".
_OPEN_PORT_RE = re.compile(
    r"\bopen\b[^\d]*\bport\b\s*(\d{1,5})|\bport\b\s*(\d{1,5})[^\d]*\bopen\b",
    re.IGNORECASE,
)

# Signals of a *real* issue on the port — presence means we must NOT downgrade.
_VULN_HINTS = (
    "vulnerab", "weak", "exposed", "default cred", "misconfig", "outdated",
    "injection", "rce", "exploit", "unauth", "anonymous", "directory listing",
    "deprecated", "self-signed", "expired", "no auth", "plaintext", "cleartext",
    "cve-",
)

_INFO_NOTE = (
    "Expected open service port with no associated vulnerability "
    "(auto-classified informational)."
)


def downgrade_expected_noise(data: dict) -> dict:
    """Return ``data`` with severity set to ``info`` when it is a bare
    expected-port observation; otherwise return it unchanged.

    A shallow copy is returned when modified so the caller's dict is untouched.
    """
    severity = (data.get("severity") or "info").lower()
    if severity in ("critical", "high", "info"):
        return data
    if data.get("cve_ids"):
        return data

    title = (data.get("title") or "").lower()
    match = _OPEN_PORT_RE.search(title)
    if not match:
        return data
    port = match.group(1) or match.group(2)
    if port not in _EXPECTED_WEB_PORTS:
        return data

    text = f"{title} {(data.get('description') or '').lower()}"
    if any(hint in text for hint in _VULN_HINTS):
        return data

    out = dict(data)
    out["severity"] = "info"
    description = (out.get("description") or "").strip()
    out["description"] = f"{description}\n\n{_INFO_NOTE}".strip() if description else _INFO_NOTE
    return out
