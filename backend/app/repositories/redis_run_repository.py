"""Redis-backed run storage implementing RunRepositoryProtocol."""
import json
import logging
from pathlib import Path
from typing import Any

import redis

from app.models.run import Run, GraphState

logger = logging.getLogger(__name__)

# Keys used for auto-migration from legacy JSON persistence
LEGACY_RUNS_FILE = Path("/app/data/runs.json")

# Redis key scheme
KEY_PREFIX = "run:"
INDEX_KEY = "runs:index"


class RedisRunRepository:
    """Run store backed by Redis with AOF persistence."""

    def __init__(self, client: redis.Redis) -> None:
        self._r = client
        self._migrate_from_json()

    # ------------------------------------------------------------------ #
    # Protocol implementation
    # ------------------------------------------------------------------ #

    def create(self, run: Run) -> None:
        pipe = self._r.pipeline()
        pipe.set(f"{KEY_PREFIX}{run.run_id}", self._serialize(run))
        pipe.sadd(INDEX_KEY, run.run_id)
        pipe.execute()

    def get(self, run_id: str) -> Run | None:
        raw = self._r.get(f"{KEY_PREFIX}{run_id}")
        if raw is None:
            return None
        return self._deserialize(raw)

    def list_runs(self) -> list[Run]:
        run_ids = self._r.smembers(INDEX_KEY)
        if not run_ids:
            return []
        keys = [f"{KEY_PREFIX}{rid}" for rid in run_ids]
        values = self._r.mget(keys)
        runs: list[Run] = []
        for val in values:
            if val is not None:
                try:
                    runs.append(self._deserialize(val))
                except Exception:
                    logger.exception("Failed to deserialize run")
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def update(self, run_id: str, updates: dict[str, Any]) -> None:
        raw = self._r.get(f"{KEY_PREFIX}{run_id}")
        if raw is None:
            return
        data = json.loads(raw)
        for k, v in updates.items():
            if k == "graph_state" and isinstance(v, dict):
                existing_gs = data.get("graph_state")
                if isinstance(existing_gs, dict):
                    merged = {**existing_gs, **v}
                    data["graph_state"] = merged
                else:
                    data["graph_state"] = v
            elif k == "graph_state" and isinstance(v, GraphState):
                dumped = v.model_dump()
                existing_gs = data.get("graph_state")
                if isinstance(existing_gs, dict):
                    data["graph_state"] = {**existing_gs, **dumped}
                else:
                    data["graph_state"] = dumped
            else:
                data[k] = v
        run = Run(**data)
        self._r.set(f"{KEY_PREFIX}{run_id}", self._serialize(run))

    def delete(self, run_id: str) -> bool:
        pipe = self._r.pipeline()
        pipe.delete(f"{KEY_PREFIX}{run_id}")
        pipe.srem(INDEX_KEY, run_id)
        results = pipe.execute()
        return bool(results[0])

    # ------------------------------------------------------------------ #
    # Serialization helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _serialize(run: Run) -> str:
        return json.dumps(run.model_dump(), default=str)

    @staticmethod
    def _deserialize(raw: str) -> Run:
        return Run(**json.loads(raw))

    # ------------------------------------------------------------------ #
    # Auto-migration from legacy JSON files
    # ------------------------------------------------------------------ #

    def _migrate_from_json(self) -> None:
        """Import runs from legacy JSON file if Redis is empty."""
        if self._r.scard(INDEX_KEY) > 0:
            return  # Redis already has data
        if not LEGACY_RUNS_FILE.exists():
            return
        try:
            raw = json.loads(LEGACY_RUNS_FILE.read_text(encoding="utf-8"))
            pipe = self._r.pipeline()
            count = 0
            for rid, data in raw.items():
                run = Run(**data)
                pipe.set(f"{KEY_PREFIX}{rid}", self._serialize(run))
                pipe.sadd(INDEX_KEY, rid)
                count += 1
            pipe.execute()
            logger.info("Migrated %d runs from %s to Redis", count, LEGACY_RUNS_FILE)
        except Exception:
            logger.exception("Failed to migrate runs from %s", LEGACY_RUNS_FILE)
