"""Run the adversarial verification pass over a completed hunt's findings.

Called at the tail of ``execute_run``. Everything here is best-effort: a
verification failure must never turn a successful hunt into a failed one, so
every path returns a summary dict instead of raising.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def verification_enabled() -> bool:
    return bool(getattr(settings, "VERIFY_FINDINGS", True))


def run_verification(run, keys_provider, event_callback=None) -> dict:
    """Verify a run's findings and persist the verdicts. Returns a counts dict."""
    from apps.findings.serializers import FindingSerializer
    from apps.findings.verification import apply_verdicts, rank_for_verification
    from redweaver_engine.crews.verify import build_verify_crew, extract_verdicts
    from redweaver_engine.llm_factory import LLMFactory

    from .crew_factory import llm_for_role

    empty = {"confirmed": 0, "false_positive": 0, "unchanged": 0, "unmatched": 0}

    if not verification_enabled():
        logger.debug("Verification disabled (VERIFY_FINDINGS=false)")
        return empty

    from apps.findings.models import FindingStatus

    candidates = rank_for_verification(
        list(run.findings.filter(status=FindingStatus.NEW)),
        limit=int(getattr(settings, "VERIFY_MAX_FINDINGS", 25)),
        min_severity=str(getattr(settings, "VERIFY_MIN_SEVERITY", "low")),
    )
    if not candidates:
        logger.debug("run %s: nothing to verify", run.id)
        return empty

    llm_factory = LLMFactory(keys_provider)
    if not llm_factory.has_api_key():
        logger.warning("run %s: skipping verification, no LLM key", run.id)
        return empty

    payload = FindingSerializer(candidates, many=True).data
    if event_callback:
        _emit(event_callback, "verification_start", {
            "agent": "verifier", "findings": len(payload),
        })

    try:
        llm = llm_for_role(llm_factory, keys_provider.get_all(), "verifier")
        crew = build_verify_crew(
            llm=llm,
            findings=list(payload),
            target=run.target or "",
            run_id=str(run.id),
        )
        result = crew.kickoff()
        verdicts = extract_verdicts(result)
    except Exception:
        logger.exception("run %s: verification crew failed", run.id)
        if event_callback:
            _emit(event_callback, "verification_error", {
                "agent": "verifier", "error": "verification pass failed",
            })
        return empty

    if not verdicts:
        logger.warning("run %s: verifier returned no verdicts", run.id)
        return empty

    try:
        counts = apply_verdicts(run, verdicts, verifier_name="verifier")
    except Exception:
        logger.exception("run %s: could not apply verdicts", run.id)
        return empty

    if event_callback:
        _emit(event_callback, "verification_complete", {"agent": "verifier", **counts})
    return counts


def _emit(callback, event_type: str, data: dict) -> None:
    try:
        callback(event_type, data)
    except Exception:
        logger.debug("verification event %s failed to publish", event_type, exc_info=True)
