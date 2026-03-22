"""Target API endpoints with type-specific validation."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_target_service
from app.dto.target import TargetCreate
from app.services.target_service import TargetService

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.post("")
def create_target(
    body: TargetCreate,
    service: TargetService = Depends(get_target_service),
):
    return service.create(body)


@router.get("")
def list_targets(
    session_id: str | None = Query(None),
    service: TargetService = Depends(get_target_service),
):
    if session_id:
        return service.list_for_session(session_id)
    return service.list_all()


@router.get("/{target_id}")
def get_target(target_id: str, service: TargetService = Depends(get_target_service)):
    return service.get_response(target_id)


@router.put("/{target_id}")
def update_target(
    target_id: str,
    body: dict,
    service: TargetService = Depends(get_target_service),
):
    return service.update(target_id, body)


@router.delete("/{target_id}")
def delete_target(target_id: str, service: TargetService = Depends(get_target_service)):
    if not service.delete(target_id):
        raise HTTPException(status_code=404, detail="Target not found")
    return {"ok": True}
