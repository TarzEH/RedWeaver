"""Tools listing."""
from fastapi import APIRouter, Depends

from app.core.deps import get_tool_service
from app.services.tool_service import ToolService

router = APIRouter()


@router.get("/api/tools")
def list_tools(tool_service: ToolService = Depends(get_tool_service)):
    """List tool names by category. Availability is stub (all false until tool layer)."""
    return tool_service.list_tools()
