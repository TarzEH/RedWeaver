"""Pure asset-inventory aggregation.

Split out of ``views.session_assets`` so the arithmetic can be tested without a
database — the suite has no pytest-django, so anything left inline in a view is
effectively untested. The view keeps the querying and scoping; everything here
is a fold over already-fetched rows.
"""
from __future__ import annotations

import re
from typing import Iterable, Protocol
from urllib.parse import urlparse

#: Severity ordering used for "which is worse" comparisons and as the canonical
#: key set of every histogram this module emits.
SEVERITY_RANK: dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}

#: Exploitability values that count as "an exploit exists for this".
EXPLOITABLE = frozenset({"proven", "likely"})

_PORT_RE = re.compile(r"port\s*(\d{1,5})")

#: Technology titles are the labelled form — "Technology detected: nginx
#: 1.18.0", "WAF detected: Cloudflare". The colon is required on purpose. The
#: looser ``detected\s+(.+?)`` this replaces also matched *negative* findings:
#: "No open ports detected on shop.example" yielded a technology literally
#: named "on shop.example", which is how the Technologies column filled up
#: with hostnames.
_TECH_RE = re.compile(r"detected\s*:\s*(.+?)(?:\s+version|\s+stack|$)")


class FindingLike(Protocol):
    """The finding fields this module reads. Keeps tests free of the ORM."""

    severity: str
    title: str
    cve_ids: list[str]
    cisa_kev: bool
    exploitability: str


def host_of(url: str | None, fallback: str | None) -> str:
    """Best-effort hostname for a finding's affected URL.

    Falls back to the run target, then to ``"unknown"`` — an asset row with no
    host is worse than useless, since it silently merges with nothing.
    """
    raw = url or ""
    parsed = urlparse(raw).hostname if "://" in raw else ""
    return parsed or raw.split("/")[0].split(":")[0] or (fallback or "") or "unknown"


def _new_asset(host: str) -> dict:
    return {
        "host": host,
        "findings": 0,
        "max_severity": "info",
        "by_severity": dict.fromkeys(SEVERITY_RANK, 0),
        "ports": set(),
        "technologies": set(),
        "cves": set(),
        "exploit_available": False,
    }


def aggregate_assets(
    rows: Iterable[tuple[str, FindingLike]],
    screenshots: dict[str, str] | None = None,
) -> list[dict]:
    """Fold ``(host, finding)`` pairs into sorted per-host asset rows.

    Each row carries the full ``by_severity`` histogram, not just the peak.
    Callers given only a max severity and a total cannot recover the split, and
    the one that tried assumed every non-peak finding was "low" — which
    reported 42 low-severity findings for a session that had two.
    """
    shots = screenshots or {}
    assets: dict[str, dict] = {}

    for host, f in rows:
        a = assets.setdefault(host, _new_asset(host))
        a["findings"] += 1

        severity = getattr(f, "severity", None) or "info"
        if severity not in SEVERITY_RANK:
            severity = "info"
        a["by_severity"][severity] += 1
        if SEVERITY_RANK[severity] > SEVERITY_RANK[a["max_severity"]]:
            a["max_severity"] = severity

        title = (getattr(f, "title", None) or "").lower()
        port = _PORT_RE.search(title)
        if port:
            a["ports"].add(int(port.group(1)))
        tech = _TECH_RE.search(title)
        if tech:
            a["technologies"].add(tech.group(1).strip()[:40])

        a["cves"].update(getattr(f, "cve_ids", None) or [])
        if getattr(f, "cisa_kev", False) or (
            getattr(f, "exploitability", "") or ""
        ).lower() in EXPLOITABLE:
            a["exploit_available"] = True

    out = [
        {
            **a,
            "ports": sorted(a["ports"]),
            "technologies": sorted(a["technologies"]),
            "cves": sorted(a["cves"]),
            "screenshot": shots.get(a["host"], ""),
        }
        for a in assets.values()
    ]
    out.sort(key=lambda x: (-SEVERITY_RANK[x["max_severity"]], -x["findings"]))
    return out
