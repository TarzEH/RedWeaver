"""Report entity — generated from findings, customizable template."""

from __future__ import annotations

from pydantic import Field

from app.domain.base import BaseEntity


class Report(BaseEntity):
    session_id: str = ""
    hunt_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    title: str = ""
    template: str = "professional"  # "professional", "executive", "custom"
    report_markdown: str = ""
    executive_summary: str = ""
    generated_by: str = ""
