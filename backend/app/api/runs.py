"""Runs CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from app.models.run import RunCreate, RunResponse
from app.core.deps import (
    get_hunt_repository,
    get_hunt_service,
    get_run_service,
    get_session_repository,
    get_workspace_repository,
)
from app.repositories.redis_hunt_repository import RedisHuntRepository
from app.repositories.redis_session_repository import RedisSessionRepository
from app.repositories.redis_workspace_repository import RedisWorkspaceRepository
from app.services.hunt_service import HuntService
from app.services.run_service import RunService

router = APIRouter()


@router.post("/api/runs", response_model=RunResponse)
def create_run(
    body: RunCreate,
    run_service: RunService = Depends(get_run_service),
):
    """Create a new run record. Hunt execution is triggered via /api/chat."""
    return run_service.create(body)


@router.get("/api/runs")
def list_runs(
    run_service: RunService = Depends(get_run_service),
    session_repo: RedisSessionRepository = Depends(get_session_repository),
    workspace_repo: RedisWorkspaceRepository = Depends(get_workspace_repository),
):
    """List runs with optional session/workspace labels for UI grouping."""
    rows = run_service.list_runs()
    return [_enrich_run_row(dict(item), session_repo, workspace_repo) for item in rows]


def _enrich_run_row(
    row: dict,
    session_repo: RedisSessionRepository,
    workspace_repo: RedisWorkspaceRepository,
) -> dict:
    out = dict(row)
    sid = out.get("session_id")
    wsid = out.get("workspace_id")
    if sid:
        sess = session_repo.get(sid)
        if sess:
            out["session_name"] = sess.name
            if not wsid:
                wsid = sess.workspace_id
                out["workspace_id"] = wsid
    if wsid:
        w = workspace_repo.get(wsid)
        if w:
            out["workspace_name"] = w.name
    return out


@router.get("/api/runs/{run_id}")
def get_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    session_repo: RedisSessionRepository = Depends(get_session_repository),
    workspace_repo: RedisWorkspaceRepository = Depends(get_workspace_repository),
):
    """Get run metadata and messages for chat thread."""
    run = run_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _enrich_run_row(run.model_dump(), session_repo, workspace_repo)


@router.delete("/api/runs/{run_id}")
def delete_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
    hunt_repo: RedisHuntRepository = Depends(get_hunt_repository),
    hunt_service: HuntService = Depends(get_hunt_service),
):
    """Delete a run. If it was started from a session hunt, removes the Hunt and session link too."""
    hunt_id = hunt_repo.get_hunt_id_for_run(run_id)
    if hunt_id:
        if not hunt_service.delete(hunt_id):
            raise HTTPException(status_code=404, detail="Run not found")
        return {"ok": True}
    if not run_service.delete_run(run_id):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"ok": True}
