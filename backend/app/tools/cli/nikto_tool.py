"""Nikto web server scanner tool."""
import json
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class NiktoTool(BaseCLITool):
    name = "nikto_scan"
    description = (
        "Scan a web server for known vulnerabilities, misconfigurations, "
        "and dangerous files using nikto. "
        "Options: tuning='1234567890abcde' to select test categories."
    )
    category = ToolCategory.VULNERABILITY
    binary_name = "nikto"
    default_timeout = 180

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = ["nikto", "-h", target.strip(), "-Format", "json", "-output", "/dev/stdout"]
        tuning = options.get("tuning")
        if tuning:
            cmd.extend(["-Tuning", tuning])
        max_time = options.get("max_time", "120s")
        cmd.extend(["-maxtime", str(max_time)])
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        # Nikto JSON output may be wrapped in an array
        try:
            data = json.loads(stdout)
            if isinstance(data, list) and data:
                data = data[0]
        except json.JSONDecodeError:
            # Fall back to raw text parsing
            return {"raw_output": stdout[:3000], "findings": []}

        vulns = data.get("vulnerabilities", [])
        findings: list[dict[str, str]] = []
        for v in vulns:
            findings.append({
                "id": v.get("id", ""),
                "method": v.get("method", ""),
                "url": v.get("url", ""),
                "description": v.get("msg", ""),
                "osvdb": v.get("OSVDB", ""),
            })
        return {
            "target": data.get("host", ""),
            "port": data.get("port", ""),
            "findings": findings,
            "count": len(findings),
        }
