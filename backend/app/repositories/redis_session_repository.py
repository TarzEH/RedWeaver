"""Redis-backed session storage."""

from __future__ import annotations

import logging
from typing import Any

import redis

from app.domain.session import Session

logger = logging.getLogger(__name__)

KEY_PREFIX = "session:"
INDEX_KEY = "sessions:all"
WORKSPACE_INDEX = "sessions:workspace:"


class RedisSessionRepository:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, session: Session) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{session.id}", session.model_dump_json())
        pipe.sadd(INDEX_KEY, session.id)
        if session.workspace_id:
            pipe.sadd(f"{WORKSPACE_INDEX}{session.workspace_id}", session.id)
        pipe.execute()

    def get(self, session_id: str) -> Session | None:
        raw = self._r.get(f"{KEY_PREFIX}{session_id}")
        return Session.model_validate_json(raw) if raw else None

    def list_for_workspace(self, workspace_id: str) -> list[Session]:
        ids = self._r.smembers(f"{WORKSPACE_INDEX}{workspace_id}")
        return self._get_many(ids)

    def list_all(self) -> list[Session]:
        ids = self._r.smembers(INDEX_KEY)
        return self._get_many(ids)

    def update(self, session_id: str, updates: dict[str, Any]) -> None:
        session = self.get(session_id)
        if not session:
            return
        data = session.model_dump()
        data.update(updates)
        updated = Session.model_validate(data)
        self._r.set(f"{KEY_PREFIX}{session_id}", updated.model_dump_json())

    def delete(self, session_id: str) -> bool:
        session = self.get(session_id)
        if not session:
            return False
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{session_id}")
        pipe.srem(INDEX_KEY, session_id)
        if session.workspace_id:
            pipe.srem(f"{WORKSPACE_INDEX}{session.workspace_id}", session_id)
        pipe.execute()
        return True

    def _get_many(self, ids: set) -> list[Session]:
        if not ids:
            return []
        keys = [f"{KEY_PREFIX}{sid}" for sid in ids]
        values = self._r.mget(keys)
        results = []
        for val in values:
            if val:
                try:
                    results.append(Session.model_validate_json(val))
                except Exception:
                    logger.exception("Failed to deserialize session")
        return sorted(results, key=lambda s: str(s.created_at), reverse=True)
