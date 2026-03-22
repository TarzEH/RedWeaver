"""Katana web crawling/spidering tool."""
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class KatanaTool(BaseCLITool):
    name = "katana_crawl"
    description = (
        "Crawl a target URL to discover endpoints, paths, JavaScript files, "
        "and parameters using katana. "
        "Options: depth=3 (crawl depth), js_crawl=true (crawl JS files)."
    )
    category = ToolCategory.WEB_DISCOVERY
    binary_name = "katana"
    default_timeout = 300

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = [
            "katana",
            "-u", target.strip(),
            "-silent",
            "-jsonl",
            "-depth", str(options.get("depth", 3)),
            "-rate-limit", str(options.get("rate_limit", 100)),
        ]
        if options.get("js_crawl"):
            cmd.append("-js-crawl")
        if scope:
            cmd.extend(["-fs", scope])  # field scope
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        results = self._safe_json_lines(stdout)
        endpoints: list[dict[str, Any]] = []
        js_files: list[str] = []
        forms: list[str] = []

        for r in results:
            url = r.get("request", {}).get("endpoint", "") or r.get("endpoint", "")
            if not url:
                continue
            endpoints.append({
                "url": url,
                "method": r.get("request", {}).get("method", "GET"),
                "source": r.get("source", ""),
            })
            if url.endswith(".js"):
                js_files.append(url)
            if r.get("tag") == "form":
                forms.append(url)

        # Deduplicate
        seen_urls = set()
        unique_endpoints = []
        for ep in endpoints:
            if ep["url"] not in seen_urls:
                seen_urls.add(ep["url"])
                unique_endpoints.append(ep)

        return {
            "endpoints": unique_endpoints,
            "js_files": list(set(js_files)),
            "forms": list(set(forms)),
            "total_crawled": len(unique_endpoints),
        }
