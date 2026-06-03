"""Celery task: generate an on-demand OffSec playbook from a run's findings."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.keys import keys_provider_for_user
from apps.observability.publisher import publish

from .crew_factory import _build_crewai_llm
from .models import Run

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_offsec_playbook(self, run_id: str) -> None:
    run = Run.objects.filter(id=run_id).select_related("created_by").first()
    if not run:
        return

    run.offsec_status = "running"
    run.save(update_fields=["offsec_status", "updated_at"])
    publish(str(run.id), "offsec_start", {"agent": "offsec"})

    from redweaver_engine.crews.offsec import build_offsec_crew
    from redweaver_engine.llm_factory import LLMFactory
    from redweaver_engine.tools.instrumentation import run_context
    from redweaver_engine.tools.registry import ToolRegistry

    from apps.findings.serializers import FindingSerializer

    kp = keys_provider_for_user(run.created_by)
    lf = LLMFactory(kp)
    if not lf.has_api_key():
        run.offsec_status = "failed"
        run.save(update_fields=["offsec_status", "updated_at"])
        publish(str(run.id), "offsec_error", {"error": "No LLM API key configured"})
        return

    keys = kp.get_all()
    llm = _build_crewai_llm(lf, keys)
    registry = ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )
    findings = FindingSerializer(run.findings.all(), many=True).data

    with run_context(str(run.id), "offsec"):
        try:
            crew = build_offsec_crew(
                llm=llm,
                registry=registry,
                target=run.target or "",
                findings=findings,
                run_id=str(run.id),
            )
            result = crew.kickoff()
            md = (getattr(result, "raw", None) or str(result) or "").strip()
            run.offsec_markdown = md
            run.offsec_status = "completed"
            run.save(update_fields=["offsec_markdown", "offsec_status", "updated_at"])
            publish(str(run.id), "offsec_complete", {"agent": "offsec", "length": len(md)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("offsec playbook failed for %s", run_id)
            run.offsec_status = "failed"
            run.save(update_fields=["offsec_status", "updated_at"])
            publish(str(run.id), "offsec_error", {"error": str(exc)})
