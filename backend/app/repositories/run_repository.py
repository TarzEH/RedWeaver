"""Run storage abstraction with JSON file persistence."""
import json
import logging
import threading
from pathlib import Path
from typing import Any, Protocol

from app.models.run import Run, GraphState

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data")
RUNS_FILE = DATA_DIR / "runs.json"


class RunRepositoryProtocol(Protocol):
    """Abstract run storage."""

    def create(self, run: Run) -> None:
        """Persist a new run."""
        ...

    def get(self, run_id: str) -> Run | None:
        """Return run by id or None."""
        ...

    def list_runs(self) -> list[Run]:
        """Return all runs, newest first."""
        ...

    def update(self, run_id: str, updates: dict[str, Any]) -> None:
        """Update run fields (e.g. status, graph_state, messages)."""
        ...

    def delete(self, run_id: str) -> bool:
        """Remove run by id. Returns True if removed."""
        ...


class InMemoryRunRepository:
    """In-memory run store with JSON file persistence."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._lock = threading.Lock()
        self._load()

    def create(self, run: Run) -> None:
        with self._lock:
            self._runs[run.run_id] = run
            self._persist()

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)

    def update(self, run_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return
            data = run.model_dump()
            for k, v in updates.items():
                if k == "graph_state" and isinstance(v, dict):
                    gs_prev = data.get("graph_state", {})
                    if isinstance(gs_prev, GraphState):
                        gs_prev = gs_prev.model_dump()
                    elif not isinstance(gs_prev, dict):
                        gs_prev = {}
                    data["graph_state"] = GraphState(**{**gs_prev, **v})
                elif k == "graph_state" and isinstance(v, GraphState):
                    gs_prev = data.get("graph_state", {})
                    if isinstance(gs_prev, GraphState):
                        gs_prev = gs_prev.model_dump()
                    elif not isinstance(gs_prev, dict):
                        gs_prev = {}
                    data["graph_state"] = GraphState(**{**gs_prev, **v.model_dump()})
                else:
                    data[k] = v
            self._runs[run_id] = Run(**data)
            self._persist()

    def delete(self, run_id: str) -> bool:
        with self._lock:
            if run_id not in self._runs:
                return False
            del self._runs[run_id]
            self._persist()
            return True

    # ---- persistence helpers ----

    def _persist(self) -> None:
        """Write all runs to JSON file. Must be called under self._lock."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                rid: run.model_dump() for rid, run in self._runs.items()
            }
            RUNS_FILE.write_text(
                json.dumps(payload, default=str, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist runs to %s", RUNS_FILE)

    def _load(self) -> None:
        """Load runs from JSON file on init."""
        if not RUNS_FILE.exists():
            return
        try:
            raw = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
            for rid, data in raw.items():
                self._runs[rid] = Run(**data)
            logger.info("Loaded %d runs from %s", len(self._runs), RUNS_FILE)
        except Exception:
            logger.exception("Failed to load runs from %s", RUNS_FILE)
