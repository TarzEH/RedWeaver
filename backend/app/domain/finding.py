"""Finding entity — first-class security finding with dedup and triage status."""

from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import Field

from app.domain.base import BaseEntity


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"
    REMEDIATED = "remediated"


class Finding(BaseEntity):
    """A security finding with dedup key for cross-hunt deduplication."""

    title: str
    severity: Severity = Severity.INFO
    description: str = ""
    affected_url: str = ""
    evidence: str | None = None
    remediation: str | None = None
    agent_source: str = ""
    tool_used: str | None = None
    cvss_score: float | None = None
    cve_ids: list[str] = Field(default_factory=list)

    # Triage
    status: FindingStatus = FindingStatus.NEW

    # Relationships
    hunt_id: str = ""
    session_id: str = ""
    target_id: str = ""

    # Deduplication
    dedup_key: str = ""

    def compute_dedup_key(self) -> str:
        """Deterministic key for cross-hunt deduplication."""
        raw = f"{self.title.lower().strip()}|{self.affected_url.lower().strip()}|{self.severity.value}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def model_post_init(self, __context: object) -> None:
        """Auto-compute dedup_key on creation."""
        if not self.dedup_key:
            self.dedup_key = self.compute_dedup_key()
