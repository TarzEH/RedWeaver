"""Huntflow tree storage abstraction with JSON file persistence."""
import json
import logging
import threading
from pathlib import Path
from typing import Protocol

from app.models.huntflow import HuntflowTree, HuntflowNode

logger = logging.getLogger(__name__)

DATA_DIR = Path("/app/data")
HUNTFLOW_FILE = DATA_DIR / "huntflows.json"


class HuntflowRepositoryProtocol(Protocol):
    """Abstract Huntflow tree storage."""

    def get_tree(self, run_id: str) -> HuntflowTree | None:
        """Return the Huntflow tree for a run, or None."""
        ...

    def create_tree(self, run_id: str, target: str) -> HuntflowTree:
        """Create and store a new Huntflow tree for a run."""
        ...

    def delete_tree(self, run_id: str) -> None:
        """Remove the Huntflow tree for a run."""
        ...

    def persist(self) -> None:
        """Flush current state to persistent storage."""
        ...


class InMemoryHuntflowRepository:
    """In-memory Huntflow tree store with JSON file persistence."""

    def __init__(self) -> None:
        self._trees: dict[str, HuntflowTree] = {}
        self._lock = threading.Lock()
        self._load()

    def get_tree(self, run_id: str) -> HuntflowTree | None:
        return self._trees.get(run_id)

    def create_tree(self, run_id: str, target: str) -> HuntflowTree:
        with self._lock:
            tree = HuntflowTree(run_id, target)
            self._trees[run_id] = tree
            self._persist()
            return tree

    def delete_tree(self, run_id: str) -> None:
        with self._lock:
            self._trees.pop(run_id, None)
            self._persist()

    def persist(self) -> None:
        """Public persist hook -- call after mutating a tree externally."""
        with self._lock:
            self._persist()

    # ---- persistence helpers ----

    def _persist(self) -> None:
        """Write all huntflow trees to JSON file. Must be called under self._lock."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload: dict = {}
            for run_id, tree in self._trees.items():
                payload[run_id] = {
                    "run_id": tree.run_id,
                    "root_id": tree.root_id,
                    "nodes": {
                        nid: node.model_dump()
                        for nid, node in tree._nodes.items()
                    },
                }
            HUNTFLOW_FILE.write_text(
                json.dumps(payload, default=str, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to persist huntflows to %s", HUNTFLOW_FILE)

    def _load(self) -> None:
        """Load huntflow trees from JSON file on init."""
        if not HUNTFLOW_FILE.exists():
            return
        try:
            raw = json.loads(HUNTFLOW_FILE.read_text(encoding="utf-8"))
            for run_id, tree_data in raw.items():
                tree = self._rebuild_tree(tree_data)
                if tree:
                    self._trees[run_id] = tree
            logger.info("Loaded %d huntflow trees from %s", len(self._trees), HUNTFLOW_FILE)
        except Exception:
            logger.exception("Failed to load huntflows from %s", HUNTFLOW_FILE)

    @staticmethod
    def _rebuild_tree(data: dict) -> HuntflowTree | None:
        """Reconstruct a HuntflowTree from serialized data without creating a
        duplicate root node."""
        run_id = data.get("run_id")
        root_id = data.get("root_id")
        nodes_raw = data.get("nodes", {})
        if not run_id or not nodes_raw:
            return None

        # Build a blank tree object -- bypass __init__ to avoid creating
        # a second root node.
        tree = object.__new__(HuntflowTree)
        tree._run_id = run_id
        tree._nodes = {}
        tree._children_index = {}
        tree._root_id = root_id

        # Re-insert every node through the internal helper so the
        # children index is rebuilt correctly.
        for nid, node_dict in nodes_raw.items():
            node = HuntflowNode(**node_dict)
            tree._nodes[node.id] = node
            parent = node.parent_id
            if parent:
                tree._children_index.setdefault(parent, []).append(node.id)
            tree._children_index.setdefault(node.id, [])

        return tree
