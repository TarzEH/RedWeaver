"""Aggregate hunt data into a structured report model."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ServiceInfo(BaseModel):
    """Discovered host/service from reconnaissance."""
    host: str
    port: int | None = None
    service: str = ""
    version: str = ""
    technologies: list[str] = Field(default_factory=list)
    status_code: int | None = None


class ReportFinding(BaseModel):
    """Structured finding for the report."""
    id: str = ""
    title: str
    severity: str = "info"
    description: str = ""
    affected_url: str = ""
    evidence: str = ""
    remediation: str = ""
    agent_source: str = ""
    tool_used: str = ""
    cvss_score: float | None = None
    cve_ids: list[str] = Field(default_factory=list)


class ReportData(BaseModel):
    """Structured data for HTML report rendering."""
    run_id: str
    target: str
    scope: str = ""
    objective: str = "comprehensive"
    generated_at: str = ""

    # Executive summary
    executive_summary: str = ""
    risk_rating: str = "Low"  # Critical / High / Medium / Low

    # Service discovery overview
    discovered_services: list[ServiceInfo] = Field(default_factory=list)
    discovered_technologies: list[str] = Field(default_factory=list)
    total_endpoints: int = 0

    # Findings
    findings: list[ReportFinding] = Field(default_factory=list)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_agent: dict[str, int] = Field(default_factory=dict)

    # Agent execution
    agents_executed: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)

    # Methodology
    methodology: str = ""

    # Remediation priorities
    remediation_priorities: list[dict[str, Any]] = Field(default_factory=list)

    # Raw report markdown (from report_writer agent)
    report_markdown: str = ""


def _compute_risk_rating(findings_by_severity: dict[str, int]) -> str:
    """Compute overall risk rating from severity counts."""
    if findings_by_severity.get("critical", 0) > 0:
        return "Critical"
    if findings_by_severity.get("high", 0) > 0:
        return "High"
    if findings_by_severity.get("medium", 0) > 0:
        return "Medium"
    if findings_by_severity.get("low", 0) > 0:
        return "Low"
    return "Informational"


def _extract_services(recon_data: dict[str, Any]) -> list[ServiceInfo]:
    """Extract service information from recon results."""
    services: list[ServiceInfo] = []

    # From nmap-style results
    for host_data in recon_data.get("hosts", []):
        host = host_data.get("host", host_data.get("ip", ""))
        for port_info in host_data.get("ports", []):
            services.append(ServiceInfo(
                host=host,
                port=port_info.get("port"),
                service=port_info.get("service", ""),
                version=port_info.get("version", ""),
            ))

    # From httpx-style results
    for probe in recon_data.get("alive_hosts", recon_data.get("probes", [])):
        if isinstance(probe, dict):
            services.append(ServiceInfo(
                host=probe.get("host", probe.get("url", "")),
                status_code=probe.get("status_code"),
                technologies=probe.get("technologies", []),
            ))
        elif isinstance(probe, str):
            services.append(ServiceInfo(host=probe))

    return services


def _extract_technologies(recon_data: dict[str, Any]) -> list[str]:
    """Extract unique technologies from recon results."""
    techs: set[str] = set()
    for item in recon_data.get("technologies", []):
        if isinstance(item, str):
            techs.add(item)
        elif isinstance(item, dict):
            name = item.get("name", item.get("technology", ""))
            version = item.get("version", "")
            if name:
                techs.add(f"{name} {version}".strip() if version else name)
    # Also from service probes
    for svc in recon_data.get("alive_hosts", []):
        if isinstance(svc, dict):
            for t in svc.get("technologies", []):
                if isinstance(t, str):
                    techs.add(t)
    return sorted(techs)


def _normalize_findings(raw_findings: list[dict[str, Any]]) -> list[ReportFinding]:
    """Normalize raw finding dicts into ReportFinding objects."""
    findings = []
    for i, f in enumerate(raw_findings):
        if not isinstance(f, dict):
            continue
        findings.append(ReportFinding(
            id=f.get("id", f"FINDING-{i+1:03d}"),
            title=f.get("title", "Untitled Finding"),
            severity=(f.get("severity", "info") or "info").lower(),
            description=f.get("description", ""),
            affected_url=f.get("affected_url", f.get("url", "")),
            evidence=f.get("evidence", ""),
            remediation=f.get("remediation", ""),
            agent_source=f.get("agent_source", f.get("agent", "")),
            tool_used=f.get("tool_used", f.get("tool", "")),
            cvss_score=f.get("cvss_score"),
            cve_ids=f.get("cve_ids", []),
        ))
    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda x: severity_order.get(x.severity, 5))
    return findings


_EXEC_SUMMARY_SECTION = re.compile(
    r"^##\s*Executive\s+summary\b[^\n]*\n[\s\S]*?(?=\n##\s[^\n#]|\n#\s[^\n#]|\Z)",
    re.IGNORECASE | re.MULTILINE,
)


def _llm_claims_zero_findings_in_narrative(markdown: str) -> bool:
    """Detect when the report_writer narrative says no findings but Redis has findings."""
    low = markdown.lower()
    if re.search(r"identified\s+0\s+finding", low):
        return True
    if re.search(
        r"0\s+critical,\s*0\s+high,\s*0\s+medium,\s*(?:0\s+low,\s*)?(?:and\s*)?0\s+informational",
        low,
    ):
        return True
    return False


def _reconcile_llm_report_markdown(
    report_markdown: str,
    executive_summary: str,
    total_findings: int,
) -> str:
    """Swap in the server-side executive summary when the LLM text contradicts stored findings."""
    md = (report_markdown or "").strip()
    if total_findings <= 0 or not md or not _llm_claims_zero_findings_in_narrative(md):
        return report_markdown
    block = f"## Executive summary\n\n{executive_summary}\n\n---\n\n"
    m = _EXEC_SUMMARY_SECTION.search(md)
    if m:
        return md[: m.start()] + block + md[m.end() :]
    return block + md


def _build_remediation_priorities(findings: list[ReportFinding]) -> list[dict[str, Any]]:
    """Build prioritized remediation list from findings."""
    priorities = []
    for f in findings:
        if f.severity in ("critical", "high", "medium") and f.remediation:
            priorities.append({
                "finding_id": f.id,
                "title": f.title,
                "severity": f.severity,
                "remediation": f.remediation,
                "cvss_score": f.cvss_score,
            })
    # Sort by CVSS score (highest first), then severity
    severity_weight = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    priorities.sort(
        key=lambda x: (-(x.get("cvss_score") or 0), severity_weight.get(x["severity"], 5))
    )
    return priorities


def generate_report_data(
    run_id: str,
    target: str,
    scope: str = "",
    objective: str = "comprehensive",
    findings: list[dict[str, Any]] | None = None,
    agents_executed: list[str] | None = None,
    recon_results: dict[str, Any] | None = None,
    report_markdown: str = "",
) -> ReportData:
    """Aggregate all hunt data into a structured ReportData model."""
    findings = findings or []
    agents_executed = agents_executed or []
    recon_results = recon_results or {}

    # Normalize findings
    report_findings = _normalize_findings(findings)

    # Severity counts
    findings_by_severity: dict[str, int] = {}
    for f in report_findings:
        findings_by_severity[f.severity] = findings_by_severity.get(f.severity, 0) + 1

    # Agent source counts
    findings_by_agent: dict[str, int] = {}
    for f in report_findings:
        if f.agent_source:
            findings_by_agent[f.agent_source] = findings_by_agent.get(f.agent_source, 0) + 1

    # Collect tools used
    tools_used = sorted({f.tool_used for f in report_findings if f.tool_used})

    # Service discovery
    discovered_services = _extract_services(recon_results)
    discovered_technologies = _extract_technologies(recon_results)

    # Risk rating
    risk_rating = _compute_risk_rating(findings_by_severity)

    # Executive summary
    total = len(report_findings)
    critical = findings_by_severity.get("critical", 0)
    high = findings_by_severity.get("high", 0)
    medium = findings_by_severity.get("medium", 0)
    low = findings_by_severity.get("low", 0)
    info = findings_by_severity.get("info", 0)

    executive_summary = (
        f"A {objective} vulnerability assessment was performed on {target}. "
        f"The assessment identified {total} finding(s): "
        f"{critical} critical, {high} high, {medium} medium, {low} low, and {info} informational. "
        f"The overall risk rating is {risk_rating}."
    )
    if critical > 0 or high > 0:
        executive_summary += (
            " Immediate attention is recommended for critical and high severity findings."
        )

    # Methodology — if completed_nodes was empty, infer contributing agents from findings
    agents_for_narrative = list(agents_executed) if agents_executed else []
    if not agents_for_narrative and findings_by_agent:
        agents_for_narrative = sorted(findings_by_agent.keys())

    methodology = (
        f"RedWeaver performed an automated {objective} security assessment using "
        f"a multi-agent architecture. The following agents contributed findings or tooling: "
        f"{', '.join(agents_for_narrative) if agents_for_narrative else 'N/A'}. "
        f"Tools utilized include: {', '.join(tools_used) if tools_used else 'automated scanning tools'}."
    )

    # Remediation priorities
    remediation_priorities = _build_remediation_priorities(report_findings)

    report_markdown = _reconcile_llm_report_markdown(
        report_markdown, executive_summary, total,
    )

    return ReportData(
        run_id=run_id,
        target=target,
        scope=scope,
        objective=objective,
        generated_at=datetime.now(timezone.utc).isoformat(),
        executive_summary=executive_summary,
        risk_rating=risk_rating,
        discovered_services=discovered_services,
        discovered_technologies=discovered_technologies,
        total_endpoints=len(discovered_services),
        findings=report_findings,
        findings_by_severity=findings_by_severity,
        findings_by_agent=findings_by_agent,
        agents_executed=agents_executed,
        tools_used=tools_used,
        methodology=methodology,
        remediation_priorities=remediation_priorities,
        report_markdown=report_markdown,  # reconciled when LLM claimed 0 findings incorrectly
    )
