"""Redis-backed huntflow tree storage implementing HuntflowRepositoryProtocol."""
import json
import logging
from pathlib import Path
from typing import Any

import redis

from app.models.huntflow import HuntflowTree, HuntflowNode

logger = logging.getLogger(__name__)

LEGACY_HUNTFLOW_FILE = Path("/app/data/huntflows.json")

KEY_PREFIX = "huntflow:"


class RedisHuntflowRepository:
    """Huntflow tree store backed by Redis with AOF persistence."""

    def __init__(self, client: redis.Redis) -> None:
        self._r = client
        self._cache: dict[str, HuntflowTree] = {}
        self._migrate_from_json()

    # ------------------------------------------------------------------ #
    # Protocol implementation
    # ------------------------------------------------------------------ #

    def get_tree(self, run_id: str) -> HuntflowTree | None:
        # Check local cache first (tree might have been mutated in-memory)
        if run_id in self._cache:
            return self._cache[run_id]
        raw = self._r.get(f"{KEY_PREFIX}{run_id}")
        if raw is None:
            return None
        tree = self._rebuild_tree(json.loads(raw))
        if tree:
            self._cache[run_id] = tree
        return tree

    def create_tree(self, run_id: str, target: str) -> HuntflowTree:
        tree = HuntflowTree(run_id, target)
        self._cache[run_id] = tree
        self._persist_tree(run_id, tree)
        return tree

    def delete_tree(self, run_id: str) -> None:
        self._cache.pop(run_id, None)
        self._r.delete(f"{KEY_PREFIX}{run_id}")

    def persist(self) -> None:
        """Flush all cached (potentially mutated) trees to Redis."""
        if not self._cache:
            return
        pipe = self._r.pipeline()
        for run_id, tree in self._cache.items():
            pipe.set(f"{KEY_PREFIX}{run_id}", self._serialize_tree(tree))
        pipe.execute()

    # ------------------------------------------------------------------ #
    # Serialization helpers
    # ------------------------------------------------------------------ #

    def _persist_tree(self, run_id: str, tree: HuntflowTree) -> None:
        self._r.set(f"{KEY_PREFIX}{run_id}", self._serialize_tree(tree))

    @staticmethod
    def _serialize_tree(tree: HuntflowTree) -> str:
        payload = {
            "run_id": tree.run_id,
            "root_id": tree.root_id,
            "nodes": {
                nid: node.model_dump()
                for nid, node in tree._nodes.items()
            },
        }
        return json.dumps(payload, default=str)

    @staticmethod
    def _rebuild_tree(data: dict) -> HuntflowTree | None:
        """Reconstruct a HuntflowTree from serialized data without creating a
        duplicate root node. Same logic as InMemoryHuntflowRepository."""
        run_id = data.get("run_id")
        root_id = data.get("root_id")
        nodes_raw = data.get("nodes", {})
        if not run_id or not nodes_raw:
            return None

        tree = object.__new__(HuntflowTree)
        tree._run_id = run_id
        tree._nodes = {}
        tree._children_index = {}
        tree._root_id = root_id

        for nid, node_dict in nodes_raw.items():
            node = HuntflowNode(**node_dict)
            tree._nodes[node.id] = node
            parent = node.parent_id
            if parent:
                tree._children_index.setdefault(parent, []).append(node.id)
            tree._children_index.setdefault(node.id, [])

        return tree

    # ------------------------------------------------------------------ #
    # Auto-migration from legacy JSON files
    # ------------------------------------------------------------------ #

    def _migrate_from_json(self) -> None:
        """Import huntflow trees from legacy JSON file if Redis is empty."""
        # Check if Redis already has huntflow data
        existing = self._r.keys(f"{KEY_PREFIX}*")
        if existing:
            return
        if not LEGACY_HUNTFLOW_FILE.exists():
            return
        try:
            raw = json.loads(LEGACY_HUNTFLOW_FILE.read_text(encoding="utf-8"))
            pipe = self._r.pipeline()
            count = 0
            for run_id, tree_data in raw.items():
                tree = self._rebuild_tree(tree_data)
                if tree:
                    pipe.set(f"{KEY_PREFIX}{run_id}", self._serialize_tree(tree))
                    count += 1
            pipe.execute()
            logger.info("Migrated %d huntflow trees from %s to Redis", count, LEGACY_HUNTFLOW_FILE)
        except Exception:
            logger.exception("Failed to migrate huntflows from %s", LEGACY_HUNTFLOW_FILE)
