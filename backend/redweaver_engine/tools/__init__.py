# RedWeaver tools: BugHuntTool protocol, CLI/HTTP tools, CrewAI adapter.
# ToolRegistry / to_crewai_tools are exposed lazily so importing lightweight
# submodules (e.g. instrumentation) does not pull in crewai.
from .base import BugHuntTool, ToolCategory

__all__ = ["BugHuntTool", "ToolCategory", "ToolRegistry", "to_crewai_tools"]


def __getattr__(name):
    if name == "ToolRegistry":
        from .registry import ToolRegistry

        return ToolRegistry
    if name == "to_crewai_tools":
        from .crewai_adapter import to_crewai_tools

        return to_crewai_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
