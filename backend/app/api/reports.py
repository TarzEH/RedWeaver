"""Report generation API endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.deps import get_run_repository
from app.reports.generator import generate_report_data
from app.reports.html_renderer import render_html_report

router = APIRouter(prefix="/api/runs", tags=["reports"])


def _get_run_or_404(run_id: str):
    """Fetch a run or raise 404."""
    repo = get_run_repository()
    run = repo.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _graph_state_as_dict(run) -> dict:
    """Normalize graph_state from Redis/Run (dict or Pydantic GraphState) for .get() access."""
    if not hasattr(run, "graph_state") or not run.graph_state:
        return {}
    gs = run.graph_state
    if isinstance(gs, dict):
        return gs
    if hasattr(gs, "model_dump"):
        return gs.model_dump()
    return {}


def _build_report_data(run_id: str):
    """Build ReportData from a completed run."""
    run = _get_run_or_404(run_id)

    # Extract data from run's graph_state (must support GraphState model, not only dict)
    graph_state = _graph_state_as_dict(run)

    findings = graph_state.get("findings", [])
    completed_nodes = graph_state.get("completed_nodes", [])

    # Primary: get report_markdown from graph_state (where hunt_execution_service stores it)
    report_markdown = graph_state.get("report_markdown", "")

    # Fallback: search messages for a long markdown-like message
    if not report_markdown and hasattr(run, "messages") and run.messages:
        for msg in reversed(run.messages):
            content = ""
            if isinstance(msg, dict):
                content = msg.get("content", "")
            elif hasattr(msg, "content"):
                content = msg.content or ""
            if content and len(content) > 200 and ("##" in content or "finding" in content.lower()):
                report_markdown = content
                break

    return generate_report_data(
        run_id=run_id,
        target=getattr(run, "target", "") or "",
        scope=getattr(run, "scope", "") or "",
        objective=getattr(run, "objective", "comprehensive") or "comprehensive",
        findings=findings,
        agents_executed=completed_nodes,
        recon_results={},  # Could be extracted from graph_state if stored
        report_markdown=report_markdown,
    )


@router.get("/{run_id}/report")
async def get_report(run_id: str):
    """Return structured report data as JSON (default endpoint)."""
    report_data = _build_report_data(run_id)
    return JSONResponse(content=report_data.model_dump())


@router.get("/{run_id}/report/html", response_class=HTMLResponse)
async def get_html_report(run_id: str):
    """Render and return the HTML vulnerability report."""
    report_data = _build_report_data(run_id)
    html = render_html_report(report_data)
    return HTMLResponse(content=html)


@router.get("/{run_id}/report/data")
async def get_report_data(run_id: str):
    """Return structured report data as JSON."""
    report_data = _build_report_data(run_id)
    return JSONResponse(content=report_data.model_dump())
