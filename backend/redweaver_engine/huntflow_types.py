"""Huntflow tree data model for live reasoning visualization.

The Huntflow tree records every agent action as a node in a parent-child
tree structure:
    [Hunt Root]
      -> [Agent Task: recon]
           -> [Reasoning: "I'll start with subdomain enumeration"]
           -> [Tool Call: subfinder_enum]
                -> [Tool Result: "Found 12 subdomains"]
           -> [Finding: "Open admin panel"]
      -> [Agent Task: fuzzer]
           -> [Tool Call: ffuf_fuzz]
                -> [Tool Result: "3 hidden paths found"]

The tree is stored as a flat dict[id -> HuntflowNode] with parent_id
pointers for O(1) insertion and O(n) subtree retrieval.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HuntflowNodeType(str, Enum):
    """Types of nodes in the Huntflow tree."""

    HUNT_ROOT = "hunt_root"
    AGENT_TASK = "agent_task"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FINDING = "finding"
    PLAN_UPDATE = "plan_update"
    HANDOFF = "handoff"
    ERROR = "error"


class HuntflowNode(BaseModel):
    """A single node in the Huntflow reasoning tree."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: str | None = None
    node_type: HuntflowNodeType
    agent_name: str = ""
    content: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HuntflowTree:
    """Manages the Huntflow reasoning tree for a single run.

    The tree is stored as a flat dict[id -> HuntflowNode] with parent_id
    pointers for O(1) node addition and O(n) subtree retrieval.
    """

    def __init__(self, run_id: str, target: str) -> None:
        self._run_id = run_id
        self._nodes: dict[str, HuntflowNode] = {}
        self._children_index: dict[str, list[str]] = {}
        self._root_id: str | None = None

        root = HuntflowNode(
            node_type=HuntflowNodeType.HUNT_ROOT,
            agent_name="orchestrator",
            content=f"Bug hunt: {target}",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._add_internal(root)
        self._root_id = root.id

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def root_id(self) -> str | None:
        return self._root_id

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def add_node(
        self,
        parent_id: str | None,
        node_type: HuntflowNodeType,
        agent_name: str = "",
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> HuntflowNode:
        """Add a new node to the tree. Returns the created node."""
        now = datetime.now(timezone.utc).isoformat()
        node = HuntflowNode(
            parent_id=parent_id or self._root_id,
            node_type=node_type,
            agent_name=agent_name,
            content=content,
            started_at=now,
            metadata=metadata or {},
        )
        self._add_internal(node)
        return node

    def complete_node(self, node_id: str) -> None:
        """Mark a node as completed with duration calculation."""
        node = self._nodes.get(node_id)
        if not node:
            return
        now = datetime.now(timezone.utc)
        node.completed_at = now.isoformat()
        if node.started_at:
            try:
                started = datetime.fromisoformat(node.started_at)
                node.duration_ms = int((now - started).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass

    def get_node(self, node_id: str) -> HuntflowNode | None:
        return self._nodes.get(node_id)

    def get_children(self, node_id: str) -> list[HuntflowNode]:
        child_ids = self._children_index.get(node_id, [])
        return [self._nodes[cid] for cid in child_ids if cid in self._nodes]

    def get_subtree(self, node_id: str) -> dict[str, Any]:
        """Return a node and all descendants as a nested dict."""
        node = self._nodes.get(node_id)
        if not node:
            return {}
        children = self.get_children(node_id)
        return {
            **node.model_dump(),
            "children": [self.get_subtree(c.id) for c in children],
        }

    def to_dict(self) -> dict[str, Any]:
        """Return the full tree as a nested dict from root."""
        if not self._root_id:
            return {}
        return {
            "run_id": self._run_id,
            "root": self.get_subtree(self._root_id),
            "total_nodes": len(self._nodes),
        }

    def get_flat_nodes(self) -> list[dict[str, Any]]:
        """Return all nodes as a flat list (for incremental SSE updates)."""
        return [n.model_dump() for n in self._nodes.values()]

    def _add_internal(self, node: HuntflowNode) -> None:
        self._nodes[node.id] = node
        parent = node.parent_id
        if parent:
            self._children_index.setdefault(parent, []).append(node.id)
        self._children_index.setdefault(node.id, [])
