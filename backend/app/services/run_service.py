"""Run creation and retrieval."""
from app.models.run import Run, RunCreate, RunResponse, GraphState
from app.repositories.run_repository import RunRepositoryProtocol


class RunService:
    """Create and list runs; delegates storage to RunRepository."""

    def __init__(self, run_repository: RunRepositoryProtocol) -> None:
        self._repo = run_repository

    def create(self, body: RunCreate) -> RunResponse:
        import uuid
        from datetime import datetime
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        user_content = f"Target: {body.target}"
        if body.scope:
            user_content += f", Scope: {body.scope}"
        user_content += f", Objective: {body.objective}"
        run = Run(
            run_id=run_id,
            target=body.target,
            scope=body.scope,
            objective=body.objective,
            status="queued",
            created_at=now,
            graph_state=GraphState(current_node="start", completed_nodes=[]),
            messages=[
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": "Run queued. Execution will start when the agent pipeline is connected.", "status": "queued"},
            ],
        )
        self._repo.create(run)
        return RunResponse(run_id=run_id, status="queued")

    def list_runs(self) -> list[dict]:
        runs = self._repo.list_runs()
        rows = []
        for r in runs:
            d = {
                "run_id": r.run_id,
                "target": r.target,
                "status": r.status,
                "created_at": r.created_at,
            }
            hid = getattr(r, "hunt_id", None)
            sid = getattr(r, "session_id", None)
            wid = getattr(r, "workspace_id", None)
            if hid:
                d["hunt_id"] = hid
            if sid:
                d["session_id"] = sid
            if wid:
                d["workspace_id"] = wid
            rows.append(d)
        return rows

    def get_run(self, run_id: str) -> Run | None:
        return self._repo.get(run_id)

    def update_run(self, run_id: str, updates: dict) -> None:
        self._repo.update(run_id, updates)

    def delete_run(self, run_id: str) -> bool:
        return self._repo.delete(run_id)
