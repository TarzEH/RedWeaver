"""Best-effort CVE enrichment — EPSS exploit-probability from FIRST.org.

EPSS (Exploit Prediction Scoring System) gives the probability a CVE will be
exploited in the wild in the next 30 days — a real-world prioritization signal
CVSS alone lacks. Lookups are cached in-process and fail open (a network hiccup
never breaks a hunt).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_EPSS_URL = "https://api.first.org/data/v1/epss"
_cache: dict[str, float | None] = {}


def epss_for(cve_ids: list[str]) -> dict[str, float]:
    """Return {cve_id: epss_probability} for the given CVEs (best-effort)."""
    ids = [c for c in (cve_ids or []) if isinstance(c, str) and c.upper().startswith("CVE-")]
    if not ids:
        return {}
    missing = [c for c in ids if c not in _cache]
    if missing:
        try:
            import httpx

            resp = httpx.get(_EPSS_URL, params={"cve": ",".join(missing[:50])}, timeout=6.0)
            data = resp.json().get("data", []) if resp.status_code == 200 else []
            seen = set()
            for row in data:
                cve = row.get("cve")
                try:
                    _cache[cve] = float(row.get("epss"))
                except (TypeError, ValueError):
                    _cache[cve] = None
                seen.add(cve)
            for c in missing:           # cache misses so we don't re-query
                if c not in seen:
                    _cache[c] = None
        except Exception as exc:        # noqa: BLE001
            logger.debug("EPSS lookup failed: %s", exc)
            for c in missing:
                _cache.setdefault(c, None)
    return {c: _cache[c] for c in ids if _cache.get(c) is not None}


def max_epss(cve_ids: list[str]) -> float | None:
    scores = epss_for(cve_ids)
    return max(scores.values()) if scores else None
