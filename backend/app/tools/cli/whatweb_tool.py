"""WhatWeb technology detection tool."""
import json as _json
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class WhatWebTool(BaseCLITool):
    name = "whatweb_detect"
    description = (
        "Detect technologies, frameworks, CMS, and server software on a target URL "
        "using whatweb. Returns identified technologies with versions."
    )
    category = ToolCategory.WEB_DISCOVERY
    binary_name = "whatweb"
    default_timeout = 120

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        aggression = options.get("aggression", 1)  # 1=stealthy, 3=aggressive
        cmd = [
            "whatweb",
            target.strip(),
            f"--log-json=/dev/stdout",
            f"-a{aggression}",
            "--color=never",
        ]
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        results = self._safe_json_lines(stdout)
        if not results:
            try:
                results = [_json.loads(stdout)]
            except _json.JSONDecodeError:
                return {"raw_output": stdout[:3000], "technologies": []}

        technologies: list[dict[str, Any]] = []
        for entry in results:
            plugins = entry.get("plugins", {})
            for plugin_name, details in plugins.items():
                tech: dict[str, Any] = {"name": plugin_name}
                if isinstance(details, dict):
                    version = details.get("version")
                    if version:
                        tech["version"] = version[0] if isinstance(version, list) else version
                    string = details.get("string")
                    if string:
                        tech["detail"] = string[0] if isinstance(string, list) else string
                technologies.append(tech)

        return {
            "url": results[0].get("target", "") if results else "",
            "technologies": technologies,
            "count": len(technologies),
        }
