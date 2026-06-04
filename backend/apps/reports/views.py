"""Report endpoints — assemble VulnerabilityReport from a run's findings."""
import csv
import io
import json
from collections import Counter

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access import run_scope_q, scoped_get_or_404
from apps.findings.serializers import FindingSerializer
from apps.hunts.models import Run

_SEV_TO_SARIF = {"critical": "error", "high": "error", "medium": "warning",
                 "low": "note", "info": "note"}

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]


def _risk_rating(sev_counts: dict) -> str:
    for sev in _SEV_ORDER:
        if sev_counts.get(sev):
            return sev.capitalize()
    return "Informational"


def _enrich_from_tools(run: Run):
    """Derive discovered services / technologies / endpoints from the persisted
    raw tool outputs (httpx, nmap, whatweb, crawler/fuzzer parsed_result)."""
    services: list[dict] = []
    techs: set[str] = set()
    endpoints = 0
    for te in run.tool_executions.all():
        pr = te.parsed_result if isinstance(te.parsed_result, dict) else {}
        for h in pr.get("alive_hosts") or []:
            if isinstance(h, dict):
                techs.update(h.get("tech") or [])
                services.append({
                    "host": h.get("url") or h.get("host") or run.target,
                    "port": h.get("port"),
                    "service": "http",
                    "version": h.get("webserver") or "",
                    "technologies": h.get("tech") or [],
                    "status_code": h.get("status_code"),
                })
        for host in pr.get("hosts") or []:
            if isinstance(host, dict):
                ip = host.get("ip") or host.get("host") or run.target
                for p in host.get("ports") or []:
                    if isinstance(p, dict):
                        services.append({
                            "host": ip, "port": p.get("port"),
                            "service": p.get("service") or p.get("name") or "",
                            "version": p.get("version") or "",
                            "technologies": [], "status_code": None,
                        })
        for p in pr.get("ports") or []:
            if isinstance(p, dict):
                services.append({
                    "host": run.target, "port": p.get("port"),
                    "service": p.get("service") or p.get("name") or "",
                    "version": p.get("version") or "",
                    "technologies": [], "status_code": None,
                })
        techs.update(pr.get("technologies") or [])
        if pr.get("technology"):
            techs.add(pr["technology"])
        for key in ("urls", "paths", "endpoints", "results", "found", "directories"):
            v = pr.get(key)
            if isinstance(v, list):
                endpoints += len(v)
    return services, sorted(t for t in techs if t), endpoints


def build_report(run: Run) -> dict:
    findings = list(run.findings.all())
    services, technologies, endpoints = _enrich_from_tools(run)
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
        "discovered_services": services,
        "discovered_technologies": technologies,
        "total_endpoints": endpoints,
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
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    return Response(build_report(run))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_report_export(request, run_id):
    """Export a run's report as ?fmt=json|csv|sarif (SARIF unlocks CI/CD).

    Note: the param is ``fmt`` (not ``format``) because DRF reserves ``format``
    for content negotiation and 404s on unknown renderer names.
    """
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    fmt = (request.query_params.get("fmt") or "json").lower()
    findings = FindingSerializer(
        run.findings.all().order_by("severity"), many=True
    ).data
    base = f"redweaver-{str(run.id)[:8]}"

    if fmt == "json":
        resp = HttpResponse(
            json.dumps(build_report(run), indent=2, default=str),
            content_type="application/json",
        )
        resp["Content-Disposition"] = f'attachment; filename="{base}.json"'
        return resp

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["severity", "title", "affected_url", "cvss_score", "cve_ids",
                    "status", "confidence", "description", "remediation"])
        for f in findings:
            w.writerow([
                f.get("severity"), f.get("title"), f.get("affected_url"),
                f.get("cvss_score"), ",".join(f.get("cve_ids") or []),
                f.get("status"), f.get("confidence"),
                (f.get("description") or "").replace("\n", " "),
                (f.get("remediation") or "").replace("\n", " "),
            ])
        resp = HttpResponse(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{base}.csv"'
        return resp

    if fmt == "sarif":
        results = []
        for f in findings:
            loc = f.get("affected_url") or run.target
            results.append({
                "ruleId": (f.get("cve_ids") or [f.get("title")])[0] or "finding",
                "level": _SEV_TO_SARIF.get((f.get("severity") or "info").lower(), "note"),
                "message": {"text": f.get("title") or "Finding"},
                "locations": (
                    [{"physicalLocation": {"artifactLocation": {"uri": loc}}}] if loc else []
                ),
                "properties": {
                    "cvss": f.get("cvss_score"),
                    "confidence": f.get("confidence"),
                    "agent": f.get("agent_source"),
                    "severity": f.get("severity"),
                },
            })
        sarif = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {
                    "name": "RedWeaver",
                    "informationUri": "https://github.com/TarzEH/RedWeaver",
                    "rules": [],
                }},
                "results": results,
            }],
        }
        resp = HttpResponse(json.dumps(sarif, indent=2), content_type="application/sarif+json")
        resp["Content-Disposition"] = f'attachment; filename="{base}.sarif"'
        return resp

    return Response({"error": f"unsupported format: {fmt}"}, status=400)
