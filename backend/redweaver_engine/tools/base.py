"""BugHuntTool protocol, ToolCategory enum, and shared types."""
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ToolCategory(str, Enum):
    """Categories for organizing security tools."""
    NETWORK = "network"
    DNS_SUBDOMAIN = "dns_subdomain"
    WEB_DISCOVERY = "web_discovery"
    VULNERABILITY = "vulnerability"
    FUZZING = "fuzzing"
    OSINT = "osint"
    WEB_SEARCH = "web_search"
    BROWSER = "browser"
    HTTP_API = "http_api"
    SSH = "ssh"
    FILE_IO = "file_io"
    KNOWLEDGE = "knowledge"


@runtime_checkable
class BugHuntTool(Protocol):
    """Protocol for bug-hunting tools (CLI, HTTP API, browser, etc.)."""

    name: str
    description: str
    category: ToolCategory

    def run(
        self, target: str, scope: str = "", options: dict[str, Any] | None = None
    ) -> str | dict[str, Any]:
        """Execute the tool synchronously. Return string or dict for the agent."""
        ...

    async def arun(
        self, target: str, scope: str = "", options: dict[str, Any] | None = None
    ) -> str | dict[str, Any]:
        """Async run."""
        ...

    def is_available(self) -> bool:
        """Check if the tool binary/service is available."""
        ...


def run_sync(
    tool: BugHuntTool,
    target: str,
    scope: str = "",
    options: dict[str, Any] | None = None,
) -> str | dict[str, Any]:
    """Run a tool synchronously."""
    return tool.run(target, scope or "", options or {})
