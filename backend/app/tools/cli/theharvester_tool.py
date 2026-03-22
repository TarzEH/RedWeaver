"""theHarvester OSINT tool for email and subdomain gathering."""
import json as _json
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class TheHarvesterTool(BaseCLITool):
    name = "theharvester_osint"
    description = (
        "Gather emails, subdomains, hosts, and other OSINT data for a domain "
        "using theHarvester. "
        "Options: source='all'|'google'|'bing'|'duckduckgo' (default: all)."
    )
    category = ToolCategory.OSINT
    binary_name = "theHarvester"
    default_timeout = 180

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        source = options.get("source", "all")
        limit = options.get("limit", 200)
        cmd = [
            "theHarvester",
            "-d", target.strip(),
            "-b", source,
            "-l", str(limit),
            "-f", "/tmp/theharvester_out",
        ]
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        emails: list[str] = []
        hosts: list[str] = []
        ips: list[str] = []

        # Try to parse the JSON output file
        try:
            with open("/tmp/theharvester_out.json") as f:
                data = _json.load(f)
            emails = data.get("emails", [])
            hosts = data.get("hosts", [])
            ips = data.get("ips", [])
        except (FileNotFoundError, _json.JSONDecodeError):
            # Fall back to parsing stdout
            section = None
            for line in stdout.splitlines():
                line = line.strip()
                if "Emails found:" in line:
                    section = "emails"
                    continue
                elif "Hosts found:" in line:
                    section = "hosts"
                    continue
                elif "IPs found:" in line:
                    section = "ips"
                    continue
                elif line.startswith("[") or line.startswith("*"):
                    section = None
                    continue

                if not line or line.startswith("-"):
                    continue

                if section == "emails" and "@" in line:
                    emails.append(line)
                elif section == "hosts" and line:
                    hosts.append(line)
                elif section == "ips" and line:
                    ips.append(line)

        return {
            "emails": emails,
            "hosts": hosts,
            "ips": ips,
            "email_count": len(emails),
            "host_count": len(hosts),
        }
