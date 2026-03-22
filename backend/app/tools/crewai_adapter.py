"""Adapt BugHuntTool to CrewAI BaseTool.

Replaces oai_adapter.py. Wraps any BugHuntTool instance as a CrewAI
BaseTool with proper _run() implementation, JSON option parsing,
and output truncation.
"""

from __future__ import annotations

import json
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from app.tools.base import BugHuntTool


class _ToolInput(BaseModel):
    """Input schema for wrapped BugHuntTools."""

    target: str = Field(description="The target URL, domain, or IP to scan.")
    scope: str = Field(default="", description="Scope constraint (e.g., '*.example.com').")
    options: str = Field(default="", description="JSON string of additional options for the tool.")


class CrewAIToolAdapter(BaseTool):
    """Wraps a BugHuntTool as a CrewAI BaseTool.

    Preserves the target/scope/options interface and provides sync execution
    with output truncation for context window protection.
    """

    name: str
    description: str
    args_schema: Type[BaseModel] = _ToolInput
    _bug_hunt_tool: BugHuntTool = PrivateAttr()

    def __init__(self, tool: BugHuntTool, **kwargs: Any) -> None:
        super().__init__(
            name=tool.name,
            description=tool.description,
            **kwargs,
        )
        self._bug_hunt_tool = tool

    def _run(
        self,
        target: str,
        scope: str = "",
        options: str = "",
    ) -> str:
        """Execute the underlying BugHuntTool synchronously."""
        parsed_options: dict[str, Any] | None = None
        if options:
            try:
                parsed_options = json.loads(options)
            except (json.JSONDecodeError, TypeError):
                parsed_options = None

        try:
            result = self._bug_hunt_tool.run(target, scope, parsed_options)
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "tool": self.name,
                "status": "failed",
                "suggestion": "Try alternative approaches or skip this tool.",
            })

        if isinstance(result, dict):
            output = json.dumps(result, indent=2, default=str)
        else:
            output = str(result)

        # Truncate to prevent context window overflow
        max_chars = 12_000
        if len(output) > max_chars:
            output = (
                output[:max_chars]
                + f"\n\n... [truncated — {len(output)} chars total, showing first {max_chars}]"
            )
        return output


def to_crewai_tool(tool: BugHuntTool) -> CrewAIToolAdapter:
    """Wrap a single BugHuntTool as a CrewAI BaseTool."""
    return CrewAIToolAdapter(tool=tool)


def to_crewai_tools(tools: list[BugHuntTool]) -> list[BaseTool]:
    """Convert a list of BugHuntTools to CrewAI BaseTools.

    Only includes tools that are available (binary installed, API key set, etc.).
    """
    return [to_crewai_tool(t) for t in tools if t.is_available()]
