"""Target entities — rich target types with type-specific configuration.

Uses a discriminated union pattern: the `target_type` field determines
which concrete model is used for validation and serialization.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import Field

from app.domain.base import BaseEntity


class TargetType(str, Enum):
    WEBAPP = "webapp"
    API = "api"
    NETWORK = "network"
    HOST = "host"
    IDENTITY = "identity"


class SSHConfig(BaseEntity):
    """SSH connection configuration for host targets."""

    host: str = ""
    username: str = "root"
    password: str | None = None
    key_path: str | None = None
    port: int = 22


class TargetBase(BaseEntity):
    """Shared fields for all target types."""

    name: str
    target_type: TargetType
    session_id: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


class WebAppTarget(TargetBase):
    target_type: Literal[TargetType.WEBAPP] = TargetType.WEBAPP
    url: str
    tech_stack: list[str] = Field(default_factory=list)
    auth_config: dict[str, Any] = Field(default_factory=dict)


class APITarget(TargetBase):
    target_type: Literal[TargetType.API] = TargetType.API
    base_url: str
    spec_url: str | None = None
    auth_headers: dict[str, str] = Field(default_factory=dict)


class NetworkTarget(TargetBase):
    target_type: Literal[TargetType.NETWORK] = TargetType.NETWORK
    cidr_ranges: list[str] = Field(default_factory=list)
    port_ranges: str = "1-65535"


class HostTarget(TargetBase):
    target_type: Literal[TargetType.HOST] = TargetType.HOST
    ip: str
    ssh_config: SSHConfig | None = None
    os_hint: str = ""


class IdentityTarget(TargetBase):
    target_type: Literal[TargetType.IDENTITY] = TargetType.IDENTITY
    domain: str
    email_patterns: list[str] = Field(default_factory=list)


# Discriminated union for deserialization
Target = Annotated[
    Union[WebAppTarget, APITarget, NetworkTarget, HostTarget, IdentityTarget],
    Field(discriminator="target_type"),
]


def classify_target_type(target: TargetBase) -> str:
    """Map target type to CrewFactory classification ('web', 'network', 'host')."""
    mapping = {
        TargetType.WEBAPP: "web",
        TargetType.API: "web",
        TargetType.NETWORK: "network",
        TargetType.HOST: "host",
        TargetType.IDENTITY: "web",
    }
    return mapping.get(target.target_type, "web")


def target_to_string(target: TargetBase) -> str:
    """Extract the primary address string for CrewFactory compatibility."""
    if isinstance(target, WebAppTarget):
        return target.url
    if isinstance(target, APITarget):
        return target.base_url
    if isinstance(target, NetworkTarget):
        return target.cidr_ranges[0] if target.cidr_ranges else ""
    if isinstance(target, HostTarget):
        return target.ip
    if isinstance(target, IdentityTarget):
        return target.domain
    return ""
