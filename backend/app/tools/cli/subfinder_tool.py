"""Subfinder subdomain enumeration tool."""
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class SubfinderTool(BaseCLITool):
    name = "subfinder_enum"
    description = (
        "Enumerate subdomains for a root domain using subfinder. "
        "Returns a list of discovered subdomains. "
        "Options: recursive=true for recursive enumeration."
    )
    category = ToolCategory.DNS_SUBDOMAIN
    binary_name = "subfinder"
    default_timeout = 120

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        cmd = ["subfinder", "-d", target.strip(), "-silent"]
        if options.get("recursive"):
            cmd.append("-recursive")
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        subdomains = [
            line.strip()
            for line in stdout.strip().splitlines()
            if line.strip()
        ]
        return {
            "subdomains": subdomains,
            "count": len(subdomains),
        }
