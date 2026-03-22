"""Findings endpoints — both legacy (per-run) and new first-class findings API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.deps import get_run_repository, get_finding_service
from app.domain.finding import FindingStatus
from app.repositories.run_repository import RunRepositoryProtocol
from app.services.finding_service import FindingService

router = APIRouter()


# ── Legacy endpoint (backward compat) ──

@router.get("/api/runs/{run_id}/findings")
def get_run_findings(
    run_id: str,
    run_repository: RunRepositoryProtocol = Depends(get_run_repository),
    finding_service: FindingService = Depends(get_finding_service),
):
    """Get findings for a run — checks both first-class findings and graph_state fallback."""
    run = run_repository.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Try first-class findings first
    findings = finding_service.list_for_hunt(run_id)
    if findings:
        return {
            "run_id": run_id,
            "findings": [f.model_dump(mode="json") for f in findings],
            "count": len(findings),
        }

    # Fallback to graph_state
    gs_findings = []
    gs = run.graph_state
    if gs and hasattr(gs, "findings"):
        gs_findings = gs.findings or []
    elif isinstance(gs, dict):
        gs_findings = gs.get("findings", [])

    return {"run_id": run_id, "findings": gs_findings, "count": len(gs_findings)}


# ── New first-class findings API ──

@router.get("/api/findings")
def list_findings(
    session_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    severity: str | None = Query(None),
    status: str | None = Query(None),
    agent_source: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    finding_service: FindingService = Depends(get_finding_service),
):
    """Query findings with filters and pagination."""
    items, total = finding_service.list_filtered(
        session_id=session_id,
        hunt_id=hunt_id,
        severity=severity,
        status=status,
        agent_source=agent_source,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [f.model_dump(mode="json") for f in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
    }


@router.get("/api/findings/aggregate")
def aggregate_findings(
    session_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    finding_service: FindingService = Depends(get_finding_service),
):
    """Aggregate findings by severity, status, and agent."""
    return finding_service.aggregate(session_id=session_id, hunt_id=hunt_id)


@router.get("/api/findings/export")
def export_findings(
    session_id: str | None = Query(None),
    hunt_id: str | None = Query(None),
    finding_service: FindingService = Depends(get_finding_service),
):
    """Export findings as CSV."""
    csv_content = finding_service.export_csv(session_id=session_id, hunt_id=hunt_id)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=findings.csv"},
    )


@router.get("/api/findings/{finding_id}")
def get_finding(
    finding_id: str,
    finding_service: FindingService = Depends(get_finding_service),
):
    """Get a single finding by ID."""
    finding = finding_service.get(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding.model_dump(mode="json")


@router.patch("/api/findings/{finding_id}")
def update_finding_status(
    finding_id: str,
    body: dict,
    finding_service: FindingService = Depends(get_finding_service),
):
    """Triage a finding by updating its status."""
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(status_code=422, detail="status field required")
    try:
        status = FindingStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status: {new_status}. Valid: {[s.value for s in FindingStatus]}")

    finding = finding_service.update_status(finding_id, status)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding.model_dump(mode="json")
