"""Run and graph state models."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RunCreate(BaseModel):
    target: str
    scope: str | None = None
    objective: str = "comprehensive"


class RunResponse(BaseModel):
    run_id: str
    status: str


class GraphState(BaseModel):
    """UI-facing graph state for a run."""
    current_node: str | None = None
    active_nodes: list[str] = []
    completed_nodes: list[str] = []
    plan: list[str] = []
    steps: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    report_markdown: str = ""

    class Config:
        extra = "allow"


class Run(BaseModel):
    """Domain DTO for a run (in-memory or future DB)."""
    run_id: str
    target: str
    scope: str | None
    objective: str
    status: str
    created_at: str
    graph_state: GraphState
    messages: list[dict[str, Any]]
    ssh_config: dict[str, Any] | None = None
    # When this run was started from a session hunt (workspace / project flow)
    hunt_id: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None

    class Config:
        extra = "allow"
