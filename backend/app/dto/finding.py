"""Finding DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.finding import FindingStatus, Severity


class FindingResponse(BaseModel):
    id: str
    title: str
    severity: Severity
    description: str
    affected_url: str
    evidence: str | None
    remediation: str | None
    agent_source: str
    tool_used: str | None
    cvss_score: float | None
    cve_ids: list[str]
    status: FindingStatus
    hunt_id: str
    session_id: str
    target_id: str
    dedup_key: str
    created_at: str


class FindingFilter(BaseModel):
    session_id: str | None = None
    hunt_id: str | None = None
    target_id: str | None = None
    severity: Severity | None = None
    status: FindingStatus | None = None
    agent_source: str | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 50


class FindingAggregate(BaseModel):
    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_agent: dict[str, int] = Field(default_factory=dict)
    unique_count: int = 0  # After dedup
