# RedWeaver tools: BugHuntTool protocol, CLI/HTTP tools, LangChain adapter.
# ToolRegistry / to_langchain_tools are exposed lazily so importing lightweight
# submodules (e.g. instrumentation) does not pull in heavy deps.
from .base import BugHuntTool, ToolCategory

__all__ = ["BugHuntTool", "ToolCategory", "ToolRegistry", "to_langchain_tools"]


def __getattr__(name):
    if name == "ToolRegistry":
        from .registry import ToolRegistry

        return ToolRegistry
    if name == "to_langchain_tools":
        from .langchain_adapter import to_langchain_tools

        return to_langchain_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
