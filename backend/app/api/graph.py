"""Graph schema for UI: multi-agent hunt workflow."""
from fastapi import APIRouter, Depends

from app.core.deps import get_run_repository
from app.graph import get_graph_topology
from app.repositories.run_repository import RunRepositoryProtocol

router = APIRouter()


@router.get("/api/graph")
def get_graph(
    run_id: str | None = None,
    run_repository: RunRepositoryProtocol = Depends(get_run_repository),
):
    """Return the multi-agent flow graph. If run_id given, topology matches that run's config."""
    run = run_repository.get(run_id) if run_id else None

    topology = get_graph_topology()
    if run and run.target:
        ssh = getattr(run, "ssh_config", None)
        topology = get_graph_topology(
            target=run.target,
            objective=getattr(run, "objective", None) or "comprehensive",
            ssh_config=ssh if isinstance(ssh, dict) else None,
        )

    state = {
        "current_node": None,
        "completed_nodes": [],
        "plan": [],
        "steps": [],
    }

    if run and run.graph_state:
            gs = run.graph_state
            state = {
                "current_node": gs.current_node if hasattr(gs, "current_node") else gs.get("current_node"),
                "completed_nodes": gs.completed_nodes if hasattr(gs, "completed_nodes") else gs.get("completed_nodes", []),
                "plan": gs.plan if hasattr(gs, "plan") else gs.get("plan", []),
                "steps": gs.steps if hasattr(gs, "steps") else gs.get("steps", []),
            }

    return {
        "nodes": topology["nodes"],
        "edges": topology["edges"],
        "state": state,
    }
