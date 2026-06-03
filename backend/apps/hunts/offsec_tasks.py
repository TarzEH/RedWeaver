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
            publish(str(run.id), "offsec_research",
                    {"agent": "offsec", "msg": "researching knowledge base + web + CVEs"})
            research_md = gather_research(registry, run.target or "", findings)
            crew = build_offsec_crew(
                llm=llm,
                registry=registry,
                target=run.target or "",
                findings=findings,
                run_id=str(run.id),
                research_context=research_md,
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


def gather_research(registry, target: str, findings: list) -> str:
    """Pre-fetch grounding for the playbook IN PARALLEL: knowledge base
    (methodology), public web (exploits/PoCs), and CVE details. Returns a
    Markdown block injected into the agent prompt so recommendations cite
    real sources instead of relying on the model's own knowledge."""
    import os
    from concurrent.futures import ThreadPoolExecutor

    import httpx

    kb_url = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://knowledge:8100").rstrip("/")
    web = registry.get_tool("web_search")
    cve_tool = registry.get_tool("cvedetails_lookup")

    cves = sorted({c for f in findings for c in (f.get("cve_ids") or []) if c})
    titles = [f.get("title", "") for f in findings if f.get("title")][:6]
    kb_queries = [f"exploitation methodology {target}", "privilege escalation linux"] + titles
    web_queries = [f"{c} exploit proof of concept" for c in cves[:5]]

    def kb(q):
        try:
            r = httpx.post(f"{kb_url}/api/knowledge/query",
                           json={"query": q, "top_k": 3}, timeout=15)
            return ("kb", q, r.json().get("results", []))
        except Exception:
            return ("kb", q, [])

    def wq(q):
        try:
            res = web.run(q) if web else {}
            return ("web", q, res.get("results", []) if isinstance(res, dict) else [])
        except Exception:
            return ("web", q, [])

    def cq(c):
        try:
            return ("cve", c, cve_tool.run(c) if cve_tool else {})
        except Exception:
            return ("cve", c, {})

    jobs = [(kb, q) for q in kb_queries] + [(wq, q) for q in web_queries] + [(cq, c) for c in cves[:5]]
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in [ex.submit(fn, arg) for fn, arg in jobs]:
            try:
                results.append(fut.result(timeout=30))
            except Exception:
                pass

    kb_parts, web_parts, cve_parts = [], [], []
    for kind, q, data in results:
        if kind == "kb" and data:
            kb_parts.append(f"**KB: {q}**")
            for it in data[:3]:
                if isinstance(it, dict):
                    kb_parts.append(f"- _{it.get('file', 'kb')}_: {(it.get('content') or '')[:450]}")
        elif kind == "web" and data:
            web_parts.append(f"**Web: {q}**")
            for it in data[:3]:
                if isinstance(it, dict):
                    snip = (it.get("snippet") or it.get("body") or it.get("description") or "")[:200]
                    web_parts.append(f"- [{it.get('title', 'link')}]({it.get('url', '')}) — {snip}")
        elif kind == "cve" and data:
            cve_parts.append(f"**{q}**: {str(data)[:450]}")

    blocks = []
    if kb_parts:
        blocks.append("### Knowledge base (methodology)\n" + "\n".join(kb_parts))
    if web_parts:
        blocks.append("### Public web research\n" + "\n".join(web_parts))
    if cve_parts:
        blocks.append("### CVE details\n" + "\n".join(cve_parts))
    return "\n\n".join(blocks) if blocks else "(no external research results returned)"
