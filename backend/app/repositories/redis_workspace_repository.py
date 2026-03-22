"""Redis-backed workspace storage."""

from __future__ import annotations

import logging
from typing import Any

import redis

from app.domain.workspace import Workspace

logger = logging.getLogger(__name__)

KEY_PREFIX = "workspace:"
INDEX_KEY = "workspaces:all"
USER_INDEX = "workspaces:user:"


class RedisWorkspaceRepository:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, workspace: Workspace) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{workspace.id}", workspace.model_dump_json())
        pipe.sadd(INDEX_KEY, workspace.id)
        if workspace.owner_id:
            pipe.sadd(f"{USER_INDEX}{workspace.owner_id}", workspace.id)
        for mid in workspace.member_ids:
            pipe.sadd(f"{USER_INDEX}{mid}", workspace.id)
        pipe.execute()

    def get(self, workspace_id: str) -> Workspace | None:
        raw = self._r.get(f"{KEY_PREFIX}{workspace_id}")
        return Workspace.model_validate_json(raw) if raw else None

    def list_for_user(self, user_id: str) -> list[Workspace]:
        ids = self._r.smembers(f"{USER_INDEX}{user_id}")
        return self._get_many(ids)

    def list_all(self) -> list[Workspace]:
        ids = self._r.smembers(INDEX_KEY)
        return self._get_many(ids)

    def update(self, workspace_id: str, updates: dict[str, Any]) -> None:
        ws = self.get(workspace_id)
        if not ws:
            return
        data = ws.model_dump()
        data.update(updates)
        updated = Workspace.model_validate(data)
        self._r.set(f"{KEY_PREFIX}{workspace_id}", updated.model_dump_json())

    def delete(self, workspace_id: str) -> bool:
        ws = self.get(workspace_id)
        if not ws:
            return False
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{workspace_id}")
        pipe.srem(INDEX_KEY, workspace_id)
        pipe.execute()
        return True

    def _get_many(self, ids: set) -> list[Workspace]:
        if not ids:
            return []
        keys = [f"{KEY_PREFIX}{wid}" for wid in ids]
        values = self._r.mget(keys)
        results = []
        for val in values:
            if val:
                try:
                    results.append(Workspace.model_validate_json(val))
                except Exception:
                    logger.exception("Failed to deserialize workspace")
        return sorted(results, key=lambda w: str(w.created_at), reverse=True)
