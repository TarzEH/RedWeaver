"""Target DTOs — type-specific creation and response types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.target import TargetType


class TargetCreate(BaseModel):
    """Unified target creation — target_type determines which fields are used."""

    name: str
    target_type: TargetType
    session_id: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)

    # WebApp / API
    url: str | None = None
    base_url: str | None = None
    spec_url: str | None = None
    auth_config: dict[str, Any] = Field(default_factory=dict)
    auth_headers: dict[str, str] = Field(default_factory=dict)
    tech_stack: list[str] = Field(default_factory=list)

    # Network
    cidr_ranges: list[str] = Field(default_factory=list)
    port_ranges: str = "1-65535"

    # Host
    ip: str | None = None
    os_hint: str = ""
    ssh_host: str | None = None
    ssh_username: str = "root"
    ssh_password: str | None = None
    ssh_key_path: str | None = None
    ssh_port: int = 22

    # Identity
    domain: str | None = None
    email_patterns: list[str] = Field(default_factory=list)


class TargetResponse(BaseModel):
    id: str
    name: str
    target_type: TargetType
    session_id: str
    notes: str
    tags: list[str]
    created_at: str
    # Type-specific summary
    address: str = ""  # Primary address (url, ip, cidr, domain)
