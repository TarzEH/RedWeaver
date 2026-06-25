"""Adapt BugHuntTool to a LangChain tool (for the deepagents/LangGraph engine).

This is the LangChain twin of ``crewai_adapter.py``. The ``_run`` body is ported
verbatim — the same SSRF guard, instrumentation (tool_call/tool_result events +
ToolExecution row with raw CLI capture), and 12k truncation — so observability is
identical regardless of orchestrator. Tool invocation remains the single
chokepoint where targets are scope-checked and executions are recorded.
"""
from __future__ import annotations

import json
import time
from typing import Any

from pydantic import BaseModel, Field

from redweaver_engine.tools import instrumentation as instr
from redweaver_engine.tools.base import BugHuntTool
from redweaver_engine.tools.scope import check_target


class ToolInput(BaseModel):
    """Input schema for wrapped BugHuntTools (LangChain StructuredTool args)."""

    target: str = Field(description="The target URL, domain, or IP to scan.")
    scope: str = Field(default="", description="Scope constraint (e.g., '*.example.com').")
    options: str = Field(default="", description="JSON string of additional options for the tool.")


def _execute(
    bug_tool: BugHuntTool,
    name: str,
    bound_run_id: Any,
    bound_agent: Any,
    target: str,
    scope: str = "",
    options: str = "",
) -> str:
    """Single chokepoint: scope-guard, run, record, return truncated output."""
    parsed_options: dict[str, Any] | None = None
    if options:
        try:
            parsed_options = json.loads(options)
        except (json.JSONDecodeError, TypeError):
            parsed_options = None

    run_id, agent = instr.get_run_context()
    if not run_id:
        run_id = bound_run_id
    if not agent:
        agent = bound_agent
    instr.pop_cli_raw()  # drain any stale CLI capture before invoking

    allowed, block_reason = check_target(target)
    instr.publish_event(
        run_id, "tool_call",
        {"agent": agent, "tool": name, "input": target}, agent=agent,
    )

    start = time.monotonic()
    status, error = "success", ""
    if not allowed:
        result: Any = {
            "error": f"target blocked by scope guard: {block_reason}",
            "tool": name, "status": "blocked",
        }
        status, error = "blocked", block_reason
    else:
        try:
            result = bug_tool.run(target, scope, parsed_options)
        except Exception as e:  # noqa: BLE001
            result = {"error": str(e), "tool": name, "status": "failed"}
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
        "tool_name": name,
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
        {"agent": agent, "tool": name, "summary": output[:2000],
         "status": status, "duration_ms": duration_ms,
         "tool_execution_id": exec_id},
        agent=agent,
    )
    return output


def to_langchain_tool(tool: BugHuntTool, run_id: Any = None, agent: Any = None):
    """Wrap a single BugHuntTool as a LangChain StructuredTool."""
    from langchain_core.tools import StructuredTool

    def _run(target: str, scope: str = "", options: str = "") -> str:
        return _execute(tool, tool.name, run_id, agent, target, scope, options)

    return StructuredTool.from_function(
        func=_run,
        name=tool.name,
        description=tool.description,
        args_schema=ToolInput,
    )


def to_langchain_tools(tools: list[BugHuntTool], run_id: Any = None, agent: Any = None) -> list:
    """Convert available BugHuntTools to LangChain tools, baking run/agent context
    so concurrent (graph-parallel) nodes still record tool executions."""
    return [to_langchain_tool(t, run_id, agent) for t in tools if t.is_available()]


def crewai_tool_to_langchain(crew_tool: Any):
    """Wrap a CrewAI ``BaseTool`` (e.g. the SSH / file-IO suites) as a LangChain
    StructuredTool, reusing its name/description/args_schema and calling ``_run``.

    These tools are attached directly in the CrewAI path (not via the BugHuntTool
    adapter), so — for parity — they are wrapped here without the extra
    ToolExecution instrumentation, matching current behavior.
    """
    from langchain_core.tools import StructuredTool

    def _run(**kwargs: Any) -> Any:
        return crew_tool._run(**kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=getattr(crew_tool, "name", crew_tool.__class__.__name__),
        description=getattr(crew_tool, "description", "") or "",
        args_schema=getattr(crew_tool, "args_schema", None),
    )


def crewai_tools_to_langchain(tools: list) -> list:
    """Wrap a list of CrewAI BaseTools as LangChain tools."""
    return [crewai_tool_to_langchain(t) for t in tools]
