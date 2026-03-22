"""Knowledge API — proxy queries to the knowledge microservice + metadata."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

KNOWLEDGE_SERVICE_URL = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://knowledge:8100")

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/health")
async def knowledge_health():
    """Check knowledge service health."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{KNOWLEDGE_SERVICE_URL}/health", timeout=5.0)
            return resp.json()
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}


@router.post("/query")
async def knowledge_query(body: dict):
    """Query the knowledge base."""
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{KNOWLEDGE_SERVICE_URL}/query", json=body, timeout=30.0)
            return resp.json()
    except Exception as e:
        return {"status": "failed", "error": str(e), "results": []}
