"""Adapt BugHuntTool to CrewAI BaseTool.

Replaces oai_adapter.py. Wraps any BugHuntTool instance as a CrewAI
BaseTool with proper _run() implementation, JSON option parsing,
and output truncation.
"""

from __future__ import annotations

import json
import time
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from redweaver_engine.tools import instrumentation as instr
from redweaver_engine.tools.base import BugHuntTool


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
        """Execute the underlying BugHuntTool synchronously, recording a
        full ToolExecution row (incl. raw CLI output) and tool_call/tool_result
        events. This is the single chokepoint for ALL tool invocations."""
        parsed_options: dict[str, Any] | None = None
        if options:
            try:
                parsed_options = json.loads(options)
            except (json.JSONDecodeError, TypeError):
                parsed_options = None

        run_id, agent = instr.get_run_context()
        instr.pop_cli_raw()  # drain any stale CLI capture before invoking
        instr.publish_event(
            run_id, "tool_call",
            {"agent": agent, "tool": self.name, "input": target}, agent=agent,
        )

        start = time.monotonic()
        status, error = "success", ""
        try:
            result = self._bug_hunt_tool.run(target, scope, parsed_options)
        except Exception as e:
            result = {"error": str(e), "tool": self.name, "status": "failed"}
            status, error = "error", str(e)

        duration_ms = int((time.monotonic() - start) * 1000)

        if isinstance(result, dict):
            output = json.dumps(result, indent=2, default=str)
            parsed_result = result
        else:
            output = str(result)
            parsed_result = {"output": output}

        max_chars = 12_000
        if len(output) > max_chars:
            output = (
                output[:max_chars]
                + f"\n\n... [truncated — {len(output)} chars total, showing first {max_chars}]"
            )

        raw = instr.pop_cli_raw()
        exec_id = instr.record_tool_execution({
            "run_id": run_id,
            "agent": agent,
            "tool_name": self.name,
            "target": target,
            "scope": scope,
            "options": parsed_options or {},
            "argv": raw.argv if raw else [],
            "command_str": raw.command if raw else "",
            "raw_stdout": raw.stdout if raw else "",
            "raw_stderr": raw.stderr if raw else "",
            "exit_code": raw.exit_code if raw else None,
            "parsed_result": parsed_result,
            "truncated_for_llm": output,
            "status": status,
            "error": error,
            "duration_ms": duration_ms,
        })

        instr.publish_event(
            run_id, "tool_result",
            {"agent": agent, "tool": self.name, "summary": output[:2000],
             "status": status, "duration_ms": duration_ms,
             "tool_execution_id": exec_id},
            agent=agent,
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
