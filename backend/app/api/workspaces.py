"""Workspace API endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_workspace_service
from app.dto.workspace import WorkspaceCreate
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("")
def create_workspace(
    body: WorkspaceCreate,
    service: WorkspaceService = Depends(get_workspace_service),
):
    return service.create(body)


@router.get("")
def list_workspaces(service: WorkspaceService = Depends(get_workspace_service)):
    return service.list_all()


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, service: WorkspaceService = Depends(get_workspace_service)):
    return service.get(workspace_id)


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str, service: WorkspaceService = Depends(get_workspace_service)):
    if not service.delete(workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"ok": True}
