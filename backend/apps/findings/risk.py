"""Multi-signal risk prioritization (SSVC-inspired).

CVSS is severity, not risk. Modern prioritization (EPSS v4, CISA KEV, SSVC)
blends *impact* (CVSS) with *likelihood* (EPSS), *confirmed in-the-wild
exploitation* (KEV) and *weaponization* (public exploit / proven exploitability).
~2% of CVEs are ever exploited, so KEV/EPSS dominate the ranking.

Outputs a 0–100 ``risk_score`` and an SSVC-style ``decision``:
  act      — remediate immediately (KEV, or high impact + high likelihood)
  attend   — remediate sooner than the normal cycle
  track*   — monitor closely
  track    — no action needed now
"""
from __future__ import annotations

_EXPLOIT_WEAPONIZED = {"proven", "likely"}


def _sev_floor(severity: str) -> float:
    return {"critical": 9.0, "high": 7.0, "medium": 5.0, "low": 3.0, "info": 0.5}.get(
        (severity or "info").lower(), 0.5
    )


def compute_risk(
    *,
    cvss: float | None,
    epss: float | None,
    cisa_kev: bool,
    exploitability: str | None,
    severity: str | None,
) -> dict:
    # Fall back to a severity-derived CVSS when none was captured.
    cvss_v = float(cvss) if isinstance(cvss, (int, float)) and cvss else _sev_floor(severity)
    epss_v = float(epss) if isinstance(epss, (int, float)) else 0.0
    expl = (exploitability or "unknown").lower()
    weaponized = cisa_kev or expl in _EXPLOIT_WEAPONIZED

    # 0–100: impact 40 + likelihood 30 + confirmed-exploitation 20 + weaponized 10
    score = (cvss_v / 10.0) * 40.0
    score += epss_v * 30.0
    if cisa_kev:
        score += 20.0
    if expl == "proven":
        score += 10.0
    elif expl == "likely":
        score += 5.0
    score = round(max(0.0, min(100.0, score)), 1)

    if cisa_kev or (cvss_v >= 7.0 and epss_v >= 0.5):
        decision = "act"
    elif cvss_v >= 7.0 or epss_v >= 0.1 or weaponized:
        decision = "attend"
    elif cvss_v >= 4.0:
        decision = "track*"
    else:
        decision = "track"

    return {
        "risk_score": score,
        "decision": decision,
        "weaponized": weaponized,
        "factors": {
            "cvss": cvss_v,
            "epss": round(epss_v, 5),
            "kev": bool(cisa_kev),
            "exploitability": expl,
        },
    }


def risk_for_finding(f) -> dict:
    """Accept a Finding model instance or a dict-like finding."""
    get = (lambda k: getattr(f, k, None)) if not isinstance(f, dict) else f.get
    return compute_risk(
        cvss=get("cvss_score"),
        epss=get("epss_score"),
        cisa_kev=bool(get("cisa_kev")),
        exploitability=get("exploitability"),
        severity=get("severity"),
    )
