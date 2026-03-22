"""Workspace service — CRUD and membership management."""

from __future__ import annotations

import logging

from app.core.errors import NotFoundError
from app.domain.workspace import Workspace
from app.dto.workspace import WorkspaceCreate, WorkspaceResponse
from app.repositories.redis_workspace_repository import RedisWorkspaceRepository

logger = logging.getLogger(__name__)


class WorkspaceService:
    def __init__(self, workspace_repo: RedisWorkspaceRepository) -> None:
        self._repo = workspace_repo

    def create(self, dto: WorkspaceCreate, owner_id: str = "") -> WorkspaceResponse:
        ws = Workspace(name=dto.name, description=dto.description, owner_id=owner_id)
        if owner_id:
            ws.member_ids = [owner_id]
        self._repo.create(ws)
        logger.info("Workspace created: %s (%s)", ws.name, ws.id[:8])
        return self._to_response(ws)

    def get(self, workspace_id: str) -> WorkspaceResponse:
        ws = self._repo.get(workspace_id)
        if not ws:
            raise NotFoundError(f"Workspace {workspace_id} not found")
        return self._to_response(ws)

    def list_all(self) -> list[WorkspaceResponse]:
        return [self._to_response(ws) for ws in self._repo.list_all()]

    def list_for_user(self, user_id: str) -> list[WorkspaceResponse]:
        return [self._to_response(ws) for ws in self._repo.list_for_user(user_id)]

    def delete(self, workspace_id: str) -> bool:
        return self._repo.delete(workspace_id)

    def ensure_default(self) -> Workspace:
        """Ensure a default workspace exists (for single-user / backward compat)."""
        all_ws = self._repo.list_all()
        for ws in all_ws:
            if ws.name == "Default Workspace":
                return ws
        ws = Workspace(name="Default Workspace", description="Auto-created default workspace")
        self._repo.create(ws)
        logger.info("Created default workspace: %s", ws.id[:8])
        return ws

    @staticmethod
    def _to_response(ws: Workspace) -> WorkspaceResponse:
        return WorkspaceResponse(
            id=ws.id, name=ws.name, description=ws.description,
            owner_id=ws.owner_id, member_ids=ws.member_ids,
            created_at=str(ws.created_at),
        )
