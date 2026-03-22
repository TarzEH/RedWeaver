"""Hunt service — lifecycle management for hunts (replaces RunService).

Hunts are the new first-class entity. This service manages creation,
starting, stopping, and querying hunts within sessions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.domain.hunt import Hunt, HuntConfig, HuntStatus
from app.domain.target import SSHConfig
from app.dto.hunt import HuntCreate, HuntResponse, HuntDetail
from app.repositories.redis_hunt_repository import RedisHuntRepository
from app.repositories.run_repository import RunRepositoryProtocol
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class HuntService:
    def __init__(
        self,
        hunt_repo: RedisHuntRepository,
        session_service: SessionService,
        run_repo: RunRepositoryProtocol,
    ) -> None:
        self._repo = hunt_repo
        self._session = session_service
        self._run_repo = run_repo

    def create(self, dto: HuntCreate, user_id: str = "") -> HuntResponse:
        """Create a new hunt linked to a session and targets."""
        ssh = None
        if dto.ssh_config:
            ssh = SSHConfig(**dto.ssh_config)

        config = HuntConfig(
            objective=dto.objective,
            agent_selection=dto.agent_selection,
            timeout_seconds=dto.timeout_seconds,
            ssh_config=ssh,
        )

        hunt = Hunt(
            session_id=dto.session_id,
            target_ids=dto.target_ids,
            created_by=user_id,
            config=config,
            objective=dto.objective,
        )
        self._repo.create(hunt)
        if hunt.session_id:
            self._session.link_hunt(hunt.session_id, hunt.id)
        logger.info("Hunt created: %s (session=%s)", hunt.id[:8], hunt.session_id[:8] if hunt.session_id else "none")
        return self._to_response(hunt)

    def get(self, hunt_id: str) -> Hunt | None:
        return self._repo.get(hunt_id)

    def get_detail(self, hunt_id: str) -> HuntDetail:
        hunt = self._repo.get(hunt_id)
        if not hunt:
            raise NotFoundError(f"Hunt {hunt_id} not found")
        return self._to_detail(hunt)

    def list_all(self) -> list[HuntResponse]:
        return [self._to_response(h) for h in self._repo.list_all()]

    def list_for_session(self, session_id: str) -> list[HuntResponse]:
        return [self._to_response(h) for h in self._repo.list_for_session(session_id)]

    def update(self, hunt_id: str, updates: dict[str, Any]) -> None:
        self._repo.update(hunt_id, updates)

    def start(self, hunt_id: str) -> HuntResponse:
        """Mark a hunt as running."""
        hunt = self._repo.get(hunt_id)
        if not hunt:
            raise NotFoundError(f"Hunt {hunt_id} not found")
        if hunt.status not in (HuntStatus.QUEUED, HuntStatus.PAUSED):
            raise ValidationError(f"Cannot start hunt in {hunt.status.value} state")
        self._repo.update(hunt_id, {
            "status": HuntStatus.RUNNING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        return self._to_response(self._repo.get(hunt_id))

    def stop(self, hunt_id: str) -> HuntResponse:
        """Cancel a running hunt."""
        hunt = self._repo.get(hunt_id)
        if not hunt:
            raise NotFoundError(f"Hunt {hunt_id} not found")
        self._repo.update(hunt_id, {"status": HuntStatus.CANCELLED.value})
        return self._to_response(self._repo.get(hunt_id))

    def delete(self, hunt_id: str) -> bool:
        hunt = self._repo.get(hunt_id)
        if not hunt:
            return False
        if hunt.session_id:
            self._session.unlink_hunt(hunt.session_id, hunt_id)
        run_id = None
        if isinstance(hunt.graph_state, dict):
            run_id = hunt.graph_state.get("run_id")
        if not self._repo.delete(hunt_id):
            return False
        if run_id:
            self._run_repo.delete(run_id)
        return True

    @staticmethod
    def _to_response(h: Hunt) -> HuntResponse:
        return HuntResponse(
            id=h.id, session_id=h.session_id, target_ids=h.target_ids,
            status=h.status, target=h.target, objective=h.objective,
            finding_count=len(h.finding_ids),
            created_at=str(h.created_at),
            started_at=h.started_at, completed_at=h.completed_at,
        )

    @staticmethod
    def _to_detail(h: Hunt) -> HuntDetail:
        return HuntDetail(
            id=h.id, session_id=h.session_id, target_ids=h.target_ids,
            status=h.status, target=h.target, objective=h.objective,
            finding_count=len(h.finding_ids),
            created_at=str(h.created_at),
            started_at=h.started_at, completed_at=h.completed_at,
            messages=h.messages, graph_state=h.graph_state,
            error_message=h.error_message,
        )
