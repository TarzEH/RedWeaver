"""Health check."""
from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health():
    """Health check for Docker and frontend."""
    settings = get_settings()
    return {"status": "healthy", "service": "redweaver-backend", "version": settings.app_version}
