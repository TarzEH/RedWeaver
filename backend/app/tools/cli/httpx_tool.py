"""Httpx HTTP probing tool."""
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class HttpxTool(BaseCLITool):
    name = "httpx_probe"
    description = (
        "Probe a list of hosts/subdomains to check which are alive using httpx. "
        "Input: target can be a single host or newline-separated list. "
        "Returns alive hosts with status codes, titles, and tech info."
    )
    category = ToolCategory.WEB_DISCOVERY
    binary_name = "httpx"
    default_timeout = 180

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = [
            "httpx",
            "-silent",
            "-json",
            "-status-code",
            "-title",
            "-tech-detect",
            "-follow-redirects",
        ]
        # If target looks like a single host, use -u; otherwise pipe via stdin
        targets = [t.strip() for t in target.strip().splitlines() if t.strip()]
        if len(targets) == 1:
            cmd.extend(["-u", targets[0]])
        else:
            cmd.extend(["-l", "/dev/stdin"])
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        results = self._safe_json_lines(stdout)
        alive: list[dict[str, Any]] = []
        for r in results:
            alive.append({
                "url": r.get("url", ""),
                "status_code": r.get("status_code", 0),
                "title": r.get("title", ""),
                "tech": r.get("tech", []),
                "content_length": r.get("content_length", 0),
                "webserver": r.get("webserver", ""),
            })
        return {"alive_hosts": alive, "count": len(alive)}
