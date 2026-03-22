"""Session API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_session_service
from app.dto.session import SessionCreate
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
def create_session(
    body: SessionCreate,
    service: SessionService = Depends(get_session_service),
):
    return service.create(body)


@router.get("")
def list_sessions(
    workspace_id: str | None = Query(None),
    service: SessionService = Depends(get_session_service),
):
    if workspace_id:
        return service.list_for_workspace(workspace_id)
    return service.list_all()


@router.get("/{session_id}")
def get_session(session_id: str, service: SessionService = Depends(get_session_service)):
    return service.get(session_id)


@router.put("/{session_id}")
def update_session(
    session_id: str,
    body: dict,
    service: SessionService = Depends(get_session_service),
):
    return service.update(session_id, body)


@router.delete("/{session_id}")
def delete_session(session_id: str, service: SessionService = Depends(get_session_service)):
    if not service.delete(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.post("/{session_id}/targets/{target_id}")
def link_target(
    session_id: str, target_id: str,
    service: SessionService = Depends(get_session_service),
):
    service.link_target(session_id, target_id)
    return {"ok": True}
