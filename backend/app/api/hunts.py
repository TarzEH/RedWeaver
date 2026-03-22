"""Hunt API endpoints — first-class hunt lifecycle management.

When a hunt is started, it creates a Run (for the execution pipeline)
and kicks off the CrewAI hunt via HuntExecutionService.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import (
    get_hunt_service,
    get_hunt_execution_service,
    get_run_repository,
    get_session_repository,
    get_target_service,
)
from app.dto.hunt import HuntCreate
from app.models.run import Run, GraphState
from app.services.hunt_service import HuntService
from app.services.hunt_execution_service import HuntExecutionService
from app.services.target_service import TargetService

router = APIRouter(prefix="/api/hunts", tags=["hunts"])


@router.post("")
def create_hunt(body: HuntCreate, service: HuntService = Depends(get_hunt_service)):
    return service.create(body)


@router.get("")
def list_hunts(
    session_id: str | None = Query(None),
    service: HuntService = Depends(get_hunt_service),
):
    if session_id:
        return service.list_for_session(session_id)
    return service.list_all()


@router.get("/{hunt_id}")
def get_hunt(hunt_id: str, service: HuntService = Depends(get_hunt_service)):
    return service.get_detail(hunt_id)


@router.post("/{hunt_id}/start")
async def start_hunt(
    hunt_id: str,
    service: HuntService = Depends(get_hunt_service),
    execution_service: HuntExecutionService = Depends(get_hunt_execution_service),
    target_service: TargetService = Depends(get_target_service),
):
    """Start a hunt: creates a Run, triggers CrewAI execution, returns run_id."""
    hunt_resp = service.start(hunt_id)

    # Get the hunt entity to access target_ids and config
    hunt = service.get(hunt_id)
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")

    # Resolve target addresses for the Run
    target_strings = []
    for tid in hunt.target_ids:
        try:
            t = target_service.get(tid)
            if t:
                from app.domain.target import target_to_string
                addr = target_to_string(t)
                if addr:
                    target_strings.append(addr)
        except Exception:
            pass

    target = ", ".join(target_strings) if target_strings else hunt.target or "unknown"

    # Create a Run (the execution pipeline entity)
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    ssh_config = None
    if hunt.config and hunt.config.ssh_config:
        ssh_config = hunt.config.ssh_config.model_dump()

    workspace_id = None
    if hunt.session_id:
        sess = get_session_repository().get(hunt.session_id)
        if sess:
            workspace_id = sess.workspace_id

    run_repo = get_run_repository()
    run = Run(
        run_id=run_id,
        target=target,
        scope="",
        objective=hunt.objective or "comprehensive",
        status="running",
        created_at=now,
        graph_state=GraphState(current_node="orchestrator", completed_nodes=[]),
        messages=[{"role": "user", "content": f"Hunt target: {target}"}],
        ssh_config=ssh_config,
        hunt_id=hunt_id,
        session_id=hunt.session_id or None,
        workspace_id=workspace_id,
    )
    run_repo.create(run)

    # Link run_id back to the hunt
    service.update(hunt_id, {"target": target, "graph_state": {"run_id": run_id}})

    # Kick off execution as async task
    asyncio.create_task(execution_service.execute(run_id))

    return {
        **hunt_resp.model_dump(),
        "run_id": run_id,
    }


@router.post("/{hunt_id}/stop")
def stop_hunt(hunt_id: str, service: HuntService = Depends(get_hunt_service)):
    return service.stop(hunt_id)


@router.delete("/{hunt_id}")
def delete_hunt(hunt_id: str, service: HuntService = Depends(get_hunt_service)):
    if not service.delete(hunt_id):
        raise HTTPException(status_code=404, detail="Hunt not found")
    return {"ok": True}
