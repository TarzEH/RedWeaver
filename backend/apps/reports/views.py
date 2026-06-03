"""Report endpoints — assemble VulnerabilityReport from a run's findings."""
from collections import Counter

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.findings.serializers import FindingSerializer
from apps.hunts.models import Run

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]


def _risk_rating(sev_counts: dict) -> str:
    for sev in _SEV_ORDER:
        if sev_counts.get(sev):
            return sev.capitalize()
    return "Informational"


def build_report(run: Run) -> dict:
    findings = list(run.findings.all())
    sev_counts = Counter(f.severity for f in findings)
    agent_counts = Counter(f.agent_source for f in findings if f.agent_source)
    tools_used = sorted(
        {f.tool_used for f in findings if f.tool_used}
        | {te.tool_name for te in run.tool_executions.all()}
    )
    agents_executed = sorted({s.agent_name for s in run.agent_steps.all() if s.agent_name})
    return {
        "run_id": str(run.id),
        "target": run.target,
        "executive_summary": (run.report_markdown[:600] if run.report_markdown else ""),
        "scope": run.scope or "",
        "objective": run.objective,
        "methodology": "Automated multi-agent assessment (recon, crawl, scan, fuzz, analysis).",
        "findings": FindingSerializer(findings, many=True).data,
        "total_by_severity": dict(sev_counts),
        "findings_by_severity": dict(sev_counts),
        "report_markdown": run.report_markdown or "",
        "generated_at": run.completed_at.isoformat() if run.completed_at else run.created_at.isoformat(),
        "risk_rating": _risk_rating(sev_counts),
        "discovered_services": [],
        "discovered_technologies": [],
        "total_endpoints": 0,
        "findings_by_agent": dict(agent_counts),
        "agents_executed": agents_executed,
        "tools_used": tools_used,
        "remediation_priorities": [
            {
                "finding_id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "remediation": f.remediation,
                "cvss_score": f.cvss_score,
            }
            for f in sorted(
                findings,
                key=lambda f: _SEV_ORDER.index(f.severity) if f.severity in _SEV_ORDER else 99,
            )[:10]
        ],
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_report(request, run_id):
    run = get_object_or_404(Run, id=run_id)
    return Response(build_report(run))
