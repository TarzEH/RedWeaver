"""Nuclei vulnerability scanner tool."""
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class NucleiTool(BaseCLITool):
    name = "nuclei_scan"
    description = (
        "Scan a target URL or host for known vulnerabilities using nuclei templates. "
        "Returns structured vulnerability findings with severity. "
        "Options: severity='critical,high,medium' to filter (default: all), "
        "tags='cve,exposure' to filter by template tags."
    )
    category = ToolCategory.VULNERABILITY
    binary_name = "nuclei"
    default_timeout = 300

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = ["nuclei", "-u", target.strip(), "-jsonl", "-silent"]
        severity = options.get("severity")
        if severity:
            cmd.extend(["-severity", severity])
        tags = options.get("tags")
        if tags:
            cmd.extend(["-tags", tags])
        rate_limit = options.get("rate_limit", 100)
        cmd.extend(["-rl", str(rate_limit)])
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        results = self._safe_json_lines(stdout)
        findings: list[dict[str, Any]] = []
        for r in results:
            info = r.get("info", {})
            findings.append({
                "template_id": r.get("template-id", ""),
                "name": info.get("name", ""),
                "severity": info.get("severity", "unknown"),
                "description": info.get("description", ""),
                "matched_at": r.get("matched-at", ""),
                "matcher_name": r.get("matcher-name", ""),
                "type": r.get("type", ""),
                "host": r.get("host", ""),
                "tags": info.get("tags", []),
                "reference": info.get("reference", []),
                "cvss_score": info.get("classification", {}).get("cvss-score"),
                "cve_id": info.get("classification", {}).get("cve-id"),
            })
        return {
            "findings": findings,
            "count": len(findings),
            "by_severity": _count_by_severity(findings),
        }


def _count_by_severity(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        sev = f.get("severity", "unknown")
        counts[sev] = counts.get(sev, 0) + 1
    return counts
