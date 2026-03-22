"""Finding service — first-class CRUD, deduplication, aggregation, export."""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

from app.domain.finding import Finding, FindingStatus, Severity
from app.repositories.protocols import FindingRepositoryProtocol

logger = logging.getLogger(__name__)


class FindingService:
    """Manages security findings as first-class entities."""

    def __init__(self, finding_repo: FindingRepositoryProtocol) -> None:
        self._repo = finding_repo

    def create(self, finding: Finding) -> Finding:
        """Create a finding, auto-computing dedup key."""
        if not finding.dedup_key:
            finding.dedup_key = finding.compute_dedup_key()
        self._repo.create(finding)
        logger.info("Finding created: %s [%s] hunt=%s", finding.title, finding.severity.value, finding.hunt_id)
        return finding

    def create_from_dict(self, data: dict[str, Any], hunt_id: str = "", session_id: str = "", target_id: str = "") -> Finding:
        """Create a Finding from a raw dict (e.g., from CrewAI callback)."""
        finding = Finding(
            id=data.get("id", ""),
            title=data.get("title", "Untitled"),
            severity=Severity(data.get("severity", "info").lower()),
            description=data.get("description", ""),
            affected_url=data.get("affected_url", ""),
            evidence=data.get("evidence"),
            remediation=data.get("remediation"),
            agent_source=data.get("agent_source", ""),
            tool_used=data.get("tool_used"),
            cvss_score=data.get("cvss_score"),
            cve_ids=data.get("cve_ids", []),
            hunt_id=hunt_id,
            session_id=session_id,
            target_id=target_id,
        )
        return self.create(finding)

    def get(self, finding_id: str) -> Finding | None:
        return self._repo.get(finding_id)

    def list_for_hunt(self, hunt_id: str) -> list[Finding]:
        return self._repo.list_for_hunt(hunt_id)

    def list_for_session(self, session_id: str) -> list[Finding]:
        return self._repo.list_for_session(session_id)

    def list_filtered(
        self,
        session_id: str | None = None,
        hunt_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        agent_source: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Finding], int]:
        """Return filtered findings with total count for pagination."""
        all_findings = self._repo.list_filtered(
            session_id=session_id,
            hunt_id=hunt_id,
            severity=severity,
            status=status,
            agent_source=agent_source,
            search=search,
        )
        total = len(all_findings)
        start = (page - 1) * page_size
        end = start + page_size
        return all_findings[start:end], total

    def aggregate(self, session_id: str | None = None, hunt_id: str | None = None) -> dict[str, Any]:
        """Aggregate findings by severity, status, and agent."""
        findings = self._repo.list_filtered(session_id=session_id, hunt_id=hunt_id)

        by_severity: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        dedup_keys: set[str] = set()

        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_status[f.status.value] = by_status.get(f.status.value, 0) + 1
            by_agent[f.agent_source] = by_agent.get(f.agent_source, 0) + 1
            dedup_keys.add(f.dedup_key)

        return {
            "total": len(findings),
            "by_severity": by_severity,
            "by_status": by_status,
            "by_agent": by_agent,
            "unique_count": len(dedup_keys),
        }

    def update_status(self, finding_id: str, status: FindingStatus) -> Finding | None:
        """Triage a finding by updating its status."""
        self._repo.update_status(finding_id, status)
        finding = self._repo.get(finding_id)
        if finding:
            logger.info("Finding %s status -> %s", finding_id[:8], status.value)
        return finding

    def deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicates, keeping the first occurrence by dedup_key."""
        seen: set[str] = set()
        unique: list[Finding] = []
        for f in findings:
            key = f.dedup_key or f.compute_dedup_key()
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def export_csv(self, session_id: str | None = None, hunt_id: str | None = None) -> str:
        """Export findings as CSV string."""
        findings = self._repo.list_filtered(session_id=session_id, hunt_id=hunt_id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Title", "Severity", "Status", "Affected URL",
            "Description", "Evidence", "Remediation", "Agent",
            "Tool", "CVSS", "CVE IDs", "Hunt ID",
        ])
        for f in findings:
            writer.writerow([
                f.id, f.title, f.severity.value, f.status.value,
                f.affected_url, f.description, f.evidence or "",
                f.remediation or "", f.agent_source, f.tool_used or "",
                f.cvss_score or "", ",".join(f.cve_ids), f.hunt_id,
            ])
        return output.getvalue()
