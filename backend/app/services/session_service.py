"""Session service — CRUD and target/hunt linking."""

from __future__ import annotations

import logging

from app.core.errors import NotFoundError
from app.domain.session import Session, SessionStatus
from app.dto.session import SessionCreate, SessionResponse, SessionDetail
from app.repositories.redis_session_repository import RedisSessionRepository

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self, session_repo: RedisSessionRepository) -> None:
        self._repo = session_repo

    def create(self, dto: SessionCreate, user_id: str = "") -> SessionResponse:
        session = Session(
            name=dto.name, description=dto.description,
            workspace_id=dto.workspace_id, created_by=user_id,
            tags=dto.tags,
        )
        self._repo.create(session)
        logger.info("Session created: %s (%s)", session.name, session.id[:8])
        return self._to_response(session)

    def get(self, session_id: str) -> SessionDetail:
        session = self._repo.get(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")
        return self._to_detail(session)

    def list_for_workspace(self, workspace_id: str) -> list[SessionResponse]:
        return [self._to_response(s) for s in self._repo.list_for_workspace(workspace_id)]

    def list_all(self) -> list[SessionResponse]:
        return [self._to_response(s) for s in self._repo.list_all()]

    def update(self, session_id: str, updates: dict) -> SessionResponse:
        self._repo.update(session_id, updates)
        session = self._repo.get(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")
        return self._to_response(session)

    def delete(self, session_id: str) -> bool:
        return self._repo.delete(session_id)

    def link_target(self, session_id: str, target_id: str) -> None:
        session = self._repo.get(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")
        if target_id not in session.target_ids:
            session.target_ids.append(target_id)
            self._repo.update(session_id, {"target_ids": session.target_ids})

    def link_hunt(self, session_id: str, hunt_id: str) -> None:
        session = self._repo.get(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")
        if hunt_id not in session.hunt_ids:
            session.hunt_ids.append(hunt_id)
            self._repo.update(session_id, {"hunt_ids": session.hunt_ids})

    def unlink_hunt(self, session_id: str, hunt_id: str) -> None:
        """Remove hunt_id from session.hunt_ids (keeps Redis hunt index in sync with Session DTO)."""
        session = self._repo.get(session_id)
        if not session or hunt_id not in session.hunt_ids:
            return
        session.hunt_ids = [h for h in session.hunt_ids if h != hunt_id]
        self._repo.update(session_id, {"hunt_ids": session.hunt_ids})

    def ensure_default(self, workspace_id: str) -> Session:
        """Ensure a default session exists for backward compat."""
        sessions = self._repo.list_for_workspace(workspace_id)
        for s in sessions:
            if s.name == "Default Session":
                return s
        session = Session(name="Default Session", workspace_id=workspace_id, description="Auto-created default session")
        self._repo.create(session)
        logger.info("Created default session: %s", session.id[:8])
        return session

    @staticmethod
    def _to_response(s: Session) -> SessionResponse:
        return SessionResponse(
            id=s.id, name=s.name, description=s.description,
            workspace_id=s.workspace_id, status=s.status,
            target_count=len(s.target_ids), hunt_count=len(s.hunt_ids),
            tags=s.tags, created_at=str(s.created_at),
        )

    @staticmethod
    def _to_detail(s: Session) -> SessionDetail:
        return SessionDetail(
            id=s.id, name=s.name, description=s.description,
            workspace_id=s.workspace_id, status=s.status,
            target_count=len(s.target_ids), hunt_count=len(s.hunt_ids),
            tags=s.tags, created_at=str(s.created_at),
            target_ids=s.target_ids, hunt_ids=s.hunt_ids,
        )
