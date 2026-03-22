"""Target service — CRUD with type-specific validation and classification."""

from __future__ import annotations

import logging

from app.core.errors import NotFoundError, ValidationError
from app.domain.target import (
    TargetBase, TargetType, WebAppTarget, APITarget,
    NetworkTarget, HostTarget, IdentityTarget, SSHConfig,
    classify_target_type, target_to_string,
)
from app.dto.target import TargetCreate, TargetResponse
from app.repositories.redis_target_repository import RedisTargetRepository

logger = logging.getLogger(__name__)


class TargetService:
    def __init__(self, target_repo: RedisTargetRepository) -> None:
        self._repo = target_repo

    def create(self, dto: TargetCreate) -> TargetResponse:
        """Create a target from the DTO, dispatching to the correct type."""
        target = self._build_target(dto)
        self._repo.create(target)
        logger.info("Target created: %s [%s] (%s)", target.name, target.target_type.value, target.id[:8])
        return self._to_response(target)

    def get(self, target_id: str) -> TargetBase:
        target = self._repo.get(target_id)
        if not target:
            raise NotFoundError(f"Target {target_id} not found")
        return target

    def get_response(self, target_id: str) -> TargetResponse:
        return self._to_response(self.get(target_id))

    def list_for_session(self, session_id: str) -> list[TargetResponse]:
        return [self._to_response(t) for t in self._repo.list_for_session(session_id)]

    def list_all(self) -> list[TargetResponse]:
        return [self._to_response(t) for t in self._repo.list_all()]

    def update(self, target_id: str, updates: dict) -> TargetResponse:
        self._repo.update(target_id, updates)
        target = self._repo.get(target_id)
        if not target:
            raise NotFoundError(f"Target {target_id} not found")
        return self._to_response(target)

    def delete(self, target_id: str) -> bool:
        return self._repo.delete(target_id)

    def classify(self, target: TargetBase) -> str:
        """Classify target for CrewFactory agent selection."""
        return classify_target_type(target)

    def _build_target(self, dto: TargetCreate) -> TargetBase:
        """Build the correct concrete target type from the DTO."""
        common = {"name": dto.name, "session_id": dto.session_id, "notes": dto.notes, "tags": dto.tags}

        if dto.target_type == TargetType.WEBAPP:
            if not dto.url:
                raise ValidationError("url is required for WebApp targets")
            return WebAppTarget(url=dto.url, tech_stack=dto.tech_stack, auth_config=dto.auth_config, **common)

        if dto.target_type == TargetType.API:
            if not dto.base_url:
                raise ValidationError("base_url is required for API targets")
            return APITarget(base_url=dto.base_url, spec_url=dto.spec_url, auth_headers=dto.auth_headers, **common)

        if dto.target_type == TargetType.NETWORK:
            if not dto.cidr_ranges:
                raise ValidationError("cidr_ranges is required for Network targets")
            return NetworkTarget(cidr_ranges=dto.cidr_ranges, port_ranges=dto.port_ranges, **common)

        if dto.target_type == TargetType.HOST:
            if not dto.ip:
                raise ValidationError("ip is required for Host targets")
            ssh = None
            if dto.ssh_host:
                ssh = SSHConfig(host=dto.ssh_host, username=dto.ssh_username, password=dto.ssh_password, key_path=dto.ssh_key_path, port=dto.ssh_port)
            return HostTarget(ip=dto.ip, ssh_config=ssh, os_hint=dto.os_hint, **common)

        if dto.target_type == TargetType.IDENTITY:
            if not dto.domain:
                raise ValidationError("domain is required for Identity targets")
            return IdentityTarget(domain=dto.domain, email_patterns=dto.email_patterns, **common)

        raise ValidationError(f"Unknown target_type: {dto.target_type}")

    @staticmethod
    def _to_response(t: TargetBase) -> TargetResponse:
        return TargetResponse(
            id=t.id, name=t.name, target_type=t.target_type,
            session_id=t.session_id, notes=t.notes, tags=t.tags,
            created_at=str(t.created_at), address=target_to_string(t),
        )
