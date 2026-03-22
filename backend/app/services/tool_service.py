"""Tool listing service backed by the real ToolRegistry."""
from typing import Any, Protocol

from app.tools.registry import ToolRegistry


class ToolServiceProtocol(Protocol):
    def list_tools(self) -> dict[str, Any]: ...


class ToolService:
    """List all RedWeaver tools with their availability status."""

    def __init__(self, tool_registry: ToolRegistry | None = None) -> None:
        self._registry = tool_registry or ToolRegistry()

    def list_tools(self) -> dict[str, Any]:
        report = self._registry.get_availability_report()
        total = sum(len(tools) for tools in report.values())
        available = sum(
            1 for tools in report.values() for t in tools if t.get("available")
        )
        return {
            "categories": report,
            "total_count": total,
            "available_count": available,
        }
