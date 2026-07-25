"""Apply adversarial verification verdicts to findings.

The hunt's own exploit_analyst reports its ``false_positives`` list — the same
model grading its own homework, which reliably misses the failure mode that
matters: a confident, well-formatted finding that the evidence does not support.
The verifier is a separate pass whose only job is to *refute* each finding
against its raw evidence, and this module turns those verdicts into triage
state.

Two rules the rest of the pipeline depends on:

* **Human triage always wins.** A finding a person has already moved off
  ``new`` is never touched, so hand-labelled findings stay usable as ground
  truth for :mod:`apps.observability.calibration` and ``manage.py eval_hunt``.
* **Uncertainty changes nothing.** Only a clear verdict moves status; anything
  else adjusts confidence at most.

The scoring helpers are pure so they can be tested without a database.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VERDICT_CONFIRMED = "confirmed"
VERDICT_REFUTED = "refuted"
VERDICT_UNCERTAIN = "uncertain"

VALID_VERDICTS = (VERDICT_CONFIRMED, VERDICT_REFUTED, VERDICT_UNCERTAIN)

#: A verdict only flips status when the verifier is at least this sure.
REFUTE_THRESHOLD = 0.65
CONFIRM_THRESHOLD = 0.70

#: How much the verifier's opinion moves the stored confidence (0..1).
VERIFIER_WEIGHT = 0.5

_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def normalize_verdict(value: str) -> str:
    """Map free-form model output onto a known verdict, defaulting to uncertain."""
    v = (value or "").strip().lower()
    if v in VALID_VERDICTS:
        return v
    if v in ("false_positive", "false positive", "rejected", "refute", "not_real"):
        return VERDICT_REFUTED
    if v in ("confirm", "real", "valid", "true_positive", "true positive"):
        return VERDICT_CONFIRMED
    return VERDICT_UNCERTAIN


def status_for_verdict(
    verdict: str,
    verifier_confidence: float,
    refute_threshold: float = REFUTE_THRESHOLD,
    confirm_threshold: float = CONFIRM_THRESHOLD,
) -> str | None:
    """Return the new finding status, or None to leave the status untouched.

    ``verifier_confidence`` is how sure the verifier is *of its own verdict*,
    not how real the finding is.
    """
    verdict = normalize_verdict(verdict)
    try:
        confidence = float(verifier_confidence)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    if verdict == VERDICT_REFUTED and confidence >= refute_threshold:
        return "false_positive"
    if verdict == VERDICT_CONFIRMED and confidence >= confirm_threshold:
        return "confirmed"
    return None


def blend_confidence(
    prior: float | None,
    verdict: str,
    verifier_confidence: float,
    weight: float = VERIFIER_WEIGHT,
) -> float:
    """Fold the verifier's opinion into the heuristic confidence score.

    A refutation pulls confidence toward 0, a confirmation toward 1, and an
    uncertain verdict leaves the prior alone.
    """
    try:
        base = 0.5 if prior is None else float(prior)
    except (TypeError, ValueError):
        base = 0.5
    base = max(0.0, min(1.0, base))

    verdict = normalize_verdict(verdict)
    if verdict == VERDICT_UNCERTAIN:
        return round(base, 3)

    try:
        strength = max(0.0, min(1.0, float(verifier_confidence)))
    except (TypeError, ValueError):
        strength = 0.0

    target = 1.0 if verdict == VERDICT_CONFIRMED else 0.0
    w = max(0.0, min(1.0, weight)) * strength
    return round(base * (1 - w) + target * w, 3)


def rank_for_verification(findings, limit: int = 25, min_severity: str = "low") -> list:
    """Pick which findings are worth spending a verification call on.

    Highest severity first; anything below ``min_severity`` is skipped, since
    verifying an informational "port 443 is open" costs money and proves nothing.
    ``findings`` items may be dicts or model instances.
    """
    floor = _SEVERITY_RANK.get((min_severity or "low").lower(), 1)

    def severity_of(item) -> str:
        if isinstance(item, dict):
            return str(item.get("severity") or "info").lower()
        return str(getattr(item, "severity", "info") or "info").lower()

    eligible = [f for f in findings if _SEVERITY_RANK.get(severity_of(f), 0) >= floor]
    eligible.sort(key=lambda f: _SEVERITY_RANK.get(severity_of(f), 0), reverse=True)
    return eligible[: max(0, limit)]


def apply_verdicts(run, verdicts: list[dict], verifier_name: str = "verifier") -> dict:
    """Persist verdicts against a run's findings. Returns a counts summary.

    Matching is by exact (case-insensitive) title, the only stable handle the
    verifier is given. Unmatched verdicts are counted, not guessed at.
    """
    from .models import Finding, FindingStatus

    counts = {"confirmed": 0, "false_positive": 0, "unchanged": 0, "unmatched": 0}
    if not verdicts:
        return counts

    # Human triage is ground truth — only findings still in `new` are eligible.
    by_title: dict[str, list] = {}
    for finding in Finding.objects.filter(run=run, status=FindingStatus.NEW):
        by_title.setdefault(finding.title.strip().lower(), []).append(finding)

    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        title = str(verdict.get("title") or "").strip().lower()
        matches = by_title.get(title)
        if not matches:
            counts["unmatched"] += 1
            continue

        raw_verdict = verdict.get("verdict") or ""
        strength = verdict.get("confidence")
        new_status = status_for_verdict(raw_verdict, strength)

        for finding in matches:
            finding.confidence = blend_confidence(finding.confidence, raw_verdict, strength)
            finding.verified_by_agent = verifier_name[:64]
            fields = ["confidence", "verified_by_agent", "updated_at"]
            if new_status:
                finding.status = new_status
                fields.append("status")
                counts[new_status] += 1
            else:
                counts["unchanged"] += 1
            finding.save(update_fields=fields)

    logger.info("Verification applied to run %s: %s", run.id, counts)
    return counts
