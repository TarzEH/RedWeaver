"""Derive a data-reliability/confidence score (0..1) for a finding.

Signals (all already present in the finding payload / FindingItem schema):
CISA KEV membership, exploitability, CVSS, CVE refs, and evidence presence.
"""


def derive_confidence(data: dict) -> float:
    score = 0.4  # neutral prior

    if data.get("cisa_kev"):
        score += 0.25  # externally corroborated (in-the-wild)

    expl = (data.get("exploitability") or "unknown").lower()
    score += {"proven": 0.25, "likely": 0.15, "possible": 0.05,
              "unlikely": -0.1, "unknown": 0.0}.get(expl, 0.0)

    cvss = data.get("cvss_score")
    if isinstance(cvss, (int, float)):
        if cvss >= 9.0:
            score += 0.15
        elif cvss >= 7.0:
            score += 0.1
        elif cvss > 0:
            score += 0.05

    if data.get("cve_ids"):
        score += 0.05
    if (data.get("evidence") or "").strip():
        score += 0.1

    return max(0.0, min(1.0, round(score, 3)))
