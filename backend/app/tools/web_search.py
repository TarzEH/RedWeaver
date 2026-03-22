"""Web search tool using DuckDuckGo (free, no API key required)."""
from typing import Any

from app.tools.base import ToolCategory


class WebSearchTool:
    """Search the web for CVEs, vulnerabilities, and security information.

    Uses DuckDuckGo via the ``duckduckgo-search`` package (free).
    The ``target`` parameter is used as the search query.
    """

    name = "web_search"
    description = (
        "Search the web for security information, CVEs, known vulnerabilities, "
        "exploit details, and public disclosures. "
        "Pass a search query as the target parameter."
    )
    category = ToolCategory.WEB_SEARCH

    def __init__(self, max_results: int = 8) -> None:
        self._max_results = max_results

    def is_available(self) -> bool:
        try:
            from duckduckgo_search import DDGS  # noqa: F401
            return True
        except ImportError:
            return False

    def run(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return {"error": "duckduckgo-search package not installed"}

        query = target.strip()
        if not query:
            return {"error": "search query is required"}

        max_results = (options or {}).get("max_results", self._max_results)
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
        except Exception as e:
            return {"error": f"Search failed: {e!s}"}

        formatted: list[dict[str, str]] = []
        for r in results:
            formatted.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        return {"query": query, "results": formatted, "count": len(formatted)}

    async def arun(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        return self.run(target, scope, options)
