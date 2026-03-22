"""Tool registry: discovers, organizes, and serves tools by category and agent role."""
import os
from typing import Any

from app.tools.base import BugHuntTool, ToolCategory
from app.tools.cli import ALL_CLI_TOOLS
from app.tools.http import VirusTotalURLCheckTool, URLScanSubmitTool
from app.tools.web_search import WebSearchTool
from app.tools.cvedetails import CVEDetailsLookupTool


class ToolRegistry:
    """Central registry for all RedWeaver tools.

    Auto-discovers CLI tools, registers HTTP API tools if keys are present,
    and provides tools grouped by category or agent role.
    """

    AGENT_TOOL_MAP: dict[str, list[ToolCategory]] = {
        "recon": [
            ToolCategory.NETWORK,
            ToolCategory.DNS_SUBDOMAIN,
            ToolCategory.WEB_DISCOVERY,
            ToolCategory.HTTP_API,
            ToolCategory.OSINT,
        ],
        "crawler": [ToolCategory.WEB_DISCOVERY, ToolCategory.BROWSER],
        "vuln_scanner": [ToolCategory.VULNERABILITY],
        "fuzzer": [ToolCategory.FUZZING],
        "web_search": [ToolCategory.WEB_SEARCH, ToolCategory.VULNERABILITY],
        "exploit_analyst": [ToolCategory.WEB_SEARCH, ToolCategory.VULNERABILITY, ToolCategory.KNOWLEDGE],
        "privesc": [ToolCategory.SSH, ToolCategory.KNOWLEDGE],
        "tunnel_pivot": [ToolCategory.SSH, ToolCategory.KNOWLEDGE],
        "post_exploit": [ToolCategory.SSH, ToolCategory.FILE_IO, ToolCategory.KNOWLEDGE],
        "report_writer": [ToolCategory.FILE_IO, ToolCategory.KNOWLEDGE],
        "orchestrator": [],
        "report": [ToolCategory.FILE_IO],
    }

    def __init__(
        self,
        virustotal_api_key: str | None = None,
        urlscan_api_key: str | None = None,
    ) -> None:
        self._tools: dict[str, BugHuntTool] = {}
        self._register_cli_tools()
        self._register_http_tools(virustotal_api_key, urlscan_api_key)
        self._register_search_tools()
        self._register_cvedetails_tool()

    def _register_cli_tools(self) -> None:
        for tool_cls in ALL_CLI_TOOLS:
            tool = tool_cls()
            self._tools[tool.name] = tool

    def _register_http_tools(self, vt_key: str | None, us_key: str | None) -> None:
        vt = (vt_key or os.environ.get("VIRUSTOTAL_API_KEY", "")).strip()
        us = (us_key or os.environ.get("URLSCAN_API_KEY", "")).strip()
        if vt:
            try:
                self._tools["virustotal_url_check"] = VirusTotalURLCheckTool(vt)
            except ValueError:
                pass
        if us:
            self._tools["urlscan_submit"] = URLScanSubmitTool(us)

    def _register_search_tools(self) -> None:
        self._tools["web_search"] = WebSearchTool()

    def _register_cvedetails_tool(self) -> None:
        nvd_key = os.environ.get("NVD_API_KEY", "")
        self._tools["cvedetails_lookup"] = CVEDetailsLookupTool(nvd_key)

    def get_all_tools(self) -> list[BugHuntTool]:
        return list(self._tools.values())

    def get_tool(self, name: str) -> BugHuntTool | None:
        return self._tools.get(name)

    def get_tools_by_category(self, category: ToolCategory) -> list[BugHuntTool]:
        return [t for t in self._tools.values() if t.category == category]

    def get_tools_for_agent(self, role: str) -> list[BugHuntTool]:
        """Return tools relevant to a specific agent role, filtered to available only."""
        categories = self.AGENT_TOOL_MAP.get(role, [])
        return [
            t for t in self._tools.values()
            if t.category in categories and t.is_available()
        ]

    def get_tools_for_node(self, node_id: str) -> list[BugHuntTool]:
        """Backward-compatible alias for get_tools_for_agent."""
        return self.get_tools_for_agent(node_id)

    def get_availability_report(self) -> dict[str, list[dict[str, Any]]]:
        """Return category -> list of tools with availability status."""
        report: dict[str, list[dict[str, Any]]] = {}
        for tool in self._tools.values():
            cat = tool.category.value if hasattr(tool.category, "value") else str(tool.category)
            if cat not in report:
                report[cat] = []
            report[cat].append({
                "name": tool.name,
                "description": tool.description,
                "available": tool.is_available(),
            })
        return report
