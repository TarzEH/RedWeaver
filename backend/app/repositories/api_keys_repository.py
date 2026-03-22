"""API keys storage abstraction with JSON file persistence."""
import json
import logging
import threading
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data")
KEYS_FILE = DATA_DIR / "api_keys.json"

DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"


class ApiKeysRepositoryProtocol(Protocol):
    """Abstract API keys storage. Keys are never returned to callers; use get_all for server-side only."""

    def get_all(self) -> dict[str, str]:
        """Return all stored keys (server-side only; never expose in API response)."""
        ...

    def set_key(self, name: str, value: str) -> None:
        """Set a key by name. Empty value can mean clear."""
        ...

    def clear(self) -> None:
        """Clear all keys."""
        ...


class InMemoryApiKeysRepository:
    """In-memory API keys store with JSON file persistence."""

    def __init__(self) -> None:
        self._keys: dict[str, str] = {}
        self._lock = threading.Lock()
        self._load()

    def get_all(self) -> dict[str, str]:
        return dict(self._keys)

    def set_key(self, name: str, value: str) -> None:
        with self._lock:
            value = (value or "").strip()
            if value:
                self._keys[name] = value
            elif name in self._keys:
                del self._keys[name]
            self._persist()

    def clear(self) -> None:
        with self._lock:
            self._keys.clear()
            self._persist()

    # ---- persistence helpers ----

    def _persist(self) -> None:
        """Write all keys to JSON file. Must be called under self._lock."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            KEYS_FILE.write_text(
                json.dumps(self._keys, default=str, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist API keys to %s", KEYS_FILE)

    def _load(self) -> None:
        """Load keys from JSON file on init."""
        if not KEYS_FILE.exists():
            return
        try:
            raw = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._keys = {k: v for k, v in raw.items() if isinstance(v, str)}
            logger.info("Loaded %d API keys from %s", len(self._keys), KEYS_FILE)
        except Exception:
            logger.exception("Failed to load API keys from %s", KEYS_FILE)
