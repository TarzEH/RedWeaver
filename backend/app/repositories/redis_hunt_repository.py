"""Redis-backed hunt storage.

Hunts are the new first-class entity replacing Runs. This repository
stores Hunt domain objects and provides session-scoped queries.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis

from app.domain.hunt import Hunt

logger = logging.getLogger(__name__)

KEY_PREFIX = "hunt:"
INDEX_KEY = "hunts:all"
SESSION_INDEX = "hunts:session:"
# run_id -> hunt_id (so deleting a Run can resolve the linked Hunt / Session)
RUN_TO_HUNT_PREFIX = "hunt:run:"


class RedisHuntRepository:
    def __init__(self, client: redis.Redis) -> None:
        self._r = client

    def create(self, hunt: Hunt) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{hunt.id}", hunt.model_dump_json())
        pipe.sadd(INDEX_KEY, hunt.id)
        if hunt.session_id:
            pipe.sadd(f"{SESSION_INDEX}{hunt.session_id}", hunt.id)
        pipe.execute()

    def get(self, hunt_id: str) -> Hunt | None:
        raw = self._r.get(f"{KEY_PREFIX}{hunt_id}")
        return Hunt.model_validate_json(raw) if raw else None

    def list_all(self) -> list[Hunt]:
        ids = self._r.smembers(INDEX_KEY)
        return self._get_many(ids)

    def list_for_session(self, session_id: str) -> list[Hunt]:
        ids = self._r.smembers(f"{SESSION_INDEX}{session_id}")
        return self._get_many(ids)

    def update(self, hunt_id: str, updates: dict[str, Any]) -> None:
        hunt = self.get(hunt_id)
        if not hunt:
            return
        old_run_id = None
        if isinstance(hunt.graph_state, dict):
            old_run_id = hunt.graph_state.get("run_id")
        data = hunt.model_dump()
        data.update(updates)
        updated = Hunt.model_validate(data)
        new_run_id = None
        if isinstance(updated.graph_state, dict):
            new_run_id = updated.graph_state.get("run_id")
        pipe = self._r.pipeline()
        if old_run_id and old_run_id != new_run_id:
            pipe.delete(f"{RUN_TO_HUNT_PREFIX}{old_run_id}")
        if new_run_id:
            pipe.set(f"{RUN_TO_HUNT_PREFIX}{new_run_id}", hunt_id)
        pipe.set(f"{KEY_PREFIX}{hunt_id}", updated.model_dump_json())
        pipe.execute()

    def delete(self, hunt_id: str) -> bool:
        hunt = self.get(hunt_id)
        if not hunt:
            return False
        run_id = None
        if isinstance(hunt.graph_state, dict):
            run_id = hunt.graph_state.get("run_id")
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{hunt_id}")
        pipe.srem(INDEX_KEY, hunt_id)
        if hunt.session_id:
            pipe.srem(f"{SESSION_INDEX}{hunt.session_id}", hunt_id)
        if run_id:
            pipe.delete(f"{RUN_TO_HUNT_PREFIX}{run_id}")
        pipe.execute()
        return True

    def get_hunt_id_for_run(self, run_id: str) -> str | None:
        hid = self._r.get(f"{RUN_TO_HUNT_PREFIX}{run_id}")
        if hid:
            return hid
        # Legacy rows: graph_state had run_id before the hunt:run index existed
        for hunt_id in self._r.smembers(INDEX_KEY):
            h = self.get(hunt_id)
            if not h or not isinstance(h.graph_state, dict):
                continue
            if h.graph_state.get("run_id") == run_id:
                self._r.set(f"{RUN_TO_HUNT_PREFIX}{run_id}", hunt_id)
                return hunt_id
        return None

    def _get_many(self, ids: set) -> list[Hunt]:
        if not ids:
            return []
        keys = [f"{KEY_PREFIX}{hid}" for hid in ids]
        values = self._r.mget(keys)
        results = []
        for val in values:
            if val:
                try:
                    results.append(Hunt.model_validate_json(val))
                except Exception:
                    logger.exception("Failed to deserialize hunt")
        return sorted(results, key=lambda h: str(h.created_at), reverse=True)
