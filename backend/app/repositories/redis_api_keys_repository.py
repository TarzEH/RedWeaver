"""Redis-backed API keys storage implementing ApiKeysRepositoryProtocol."""
import json
import logging
from pathlib import Path

import redis

logger = logging.getLogger(__name__)

LEGACY_KEYS_FILE = Path("/app/data/api_keys.json")

REDIS_KEY = "keys:api"


class RedisApiKeysRepository:
    """API keys store backed by Redis with AOF persistence."""

    def __init__(self, client: redis.Redis) -> None:
        self._r = client
        self._migrate_from_json()

    # ------------------------------------------------------------------ #
    # Protocol implementation
    # ------------------------------------------------------------------ #

    def get_all(self) -> dict[str, str]:
        raw = self._r.get(REDIS_KEY)
        if raw is None:
            return {}
        try:
            data = json.loads(raw)
            return {k: v for k, v in data.items() if isinstance(v, str)}
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_key(self, name: str, value: str) -> None:
        keys = self.get_all()
        value = (value or "").strip()
        if value:
            keys[name] = value
        elif name in keys:
            del keys[name]
        self._r.set(REDIS_KEY, json.dumps(keys))

    def clear(self) -> None:
        self._r.delete(REDIS_KEY)

    # ------------------------------------------------------------------ #
    # Auto-migration from legacy JSON files
    # ------------------------------------------------------------------ #

    def _migrate_from_json(self) -> None:
        """Import API keys from legacy JSON file if Redis is empty."""
        if self._r.exists(REDIS_KEY):
            return
        if not LEGACY_KEYS_FILE.exists():
            return
        try:
            raw = json.loads(LEGACY_KEYS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw:
                self._r.set(REDIS_KEY, json.dumps(raw))
                logger.info("Migrated API keys from %s to Redis", LEGACY_KEYS_FILE)
        except Exception:
            logger.exception("Failed to migrate API keys from %s", LEGACY_KEYS_FILE)
