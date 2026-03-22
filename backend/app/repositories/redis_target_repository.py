"""Redis-backed target storage with type-aware deserialization."""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.domain.target import (
    TargetBase, TargetType, WebAppTarget, APITarget,
    NetworkTarget, HostTarget, IdentityTarget,
)

logger = logging.getLogger(__name__)

KEY_PREFIX = "target:"
INDEX_KEY = "targets:all"
SESSION_INDEX = "targets:session:"

# Map target_type to concrete class for deserialization
_TYPE_MAP = {
    TargetType.WEBAPP: WebAppTarget,
    TargetType.API: APITarget,
    TargetType.NETWORK: NetworkTarget,
    TargetType.HOST: HostTarget,
    TargetType.IDENTITY: IdentityTarget,
}


def _deserialize_target(raw: str) -> TargetBase | None:
    """Deserialize a target JSON string to the correct concrete type."""
    try:
        data = json.loads(raw)
        target_type = TargetType(data.get("target_type", "webapp"))
        cls = _TYPE_MAP.get(target_type, WebAppTarget)
        return cls.model_validate(data)
    except Exception:
        logger.exception("Failed to deserialize target")
        return None


class RedisTargetRepository:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, target: TargetBase) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{target.id}", target.model_dump_json())
        pipe.sadd(INDEX_KEY, target.id)
        if target.session_id:
            pipe.sadd(f"{SESSION_INDEX}{target.session_id}", target.id)
        pipe.execute()

    def get(self, target_id: str) -> TargetBase | None:
        raw = self._r.get(f"{KEY_PREFIX}{target_id}")
        return _deserialize_target(raw) if raw else None

    def list_for_session(self, session_id: str) -> list[TargetBase]:
        ids = self._r.smembers(f"{SESSION_INDEX}{session_id}")
        return self._get_many(ids)

    def list_all(self) -> list[TargetBase]:
        ids = self._r.smembers(INDEX_KEY)
        return self._get_many(ids)

    def update(self, target_id: str, updates: dict[str, Any]) -> None:
        target = self.get(target_id)
        if not target:
            return
        data = target.model_dump()
        data.update(updates)
        target_type = TargetType(data.get("target_type", "webapp"))
        cls = _TYPE_MAP.get(target_type, WebAppTarget)
        updated = cls.model_validate(data)
        self._r.set(f"{KEY_PREFIX}{target_id}", updated.model_dump_json())

    def delete(self, target_id: str) -> bool:
        target = self.get(target_id)
        if not target:
            return False
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{target_id}")
        pipe.srem(INDEX_KEY, target_id)
        if target.session_id:
            pipe.srem(f"{SESSION_INDEX}{target.session_id}", target_id)
        pipe.execute()
        return True

    def _get_many(self, ids: set) -> list[TargetBase]:
        if not ids:
            return []
        keys = [f"{KEY_PREFIX}{tid}" for tid in ids]
        values = self._r.mget(keys)
        results = []
        for val in values:
            if val:
                t = _deserialize_target(val)
                if t:
                    results.append(t)
        return sorted(results, key=lambda t: str(t.created_at), reverse=True)
