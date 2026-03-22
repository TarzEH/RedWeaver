"""Huntflow tree API endpoint."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_huntflow_repository
from app.repositories.huntflow_repository import HuntflowRepositoryProtocol

router = APIRouter()


@router.get("/api/runs/{run_id}/huntflow")
def get_huntflow(
    run_id: str,
    huntflow_repo: HuntflowRepositoryProtocol = Depends(get_huntflow_repository),
):
    """Return the full Huntflow reasoning tree for a run."""
    tree = huntflow_repo.get_tree(run_id)
    if not tree:
        raise HTTPException(status_code=404, detail="No huntflow tree for this run")
    return tree.to_dict()


@router.get("/api/runs/{run_id}/huntflow/{node_id}")
def get_huntflow_subtree(
    run_id: str,
    node_id: str,
    huntflow_repo: HuntflowRepositoryProtocol = Depends(get_huntflow_repository),
):
    """Return a subtree rooted at a specific node."""
    tree = huntflow_repo.get_tree(run_id)
    if not tree:
        raise HTTPException(status_code=404, detail="No huntflow tree for this run")
    subtree = tree.get_subtree(node_id)
    if not subtree:
        raise HTTPException(status_code=404, detail="Node not found")
    return subtree
