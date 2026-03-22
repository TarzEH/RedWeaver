"""Gobuster directory brute-forcing tool."""
from typing import Any

from app.tools.base import ToolCategory
from app.tools.cli.base_cli import BaseCLITool


class GobusterTool(BaseCLITool):
    name = "gobuster_dir"
    description = (
        "Brute-force directories and files on a web server using gobuster. "
        "Options: wordlist='/path/to/list' (default: common.txt), "
        "extensions='php,html,js' to append file extensions."
    )
    category = ToolCategory.FUZZING
    binary_name = "gobuster"
    default_timeout = 300

    DEFAULT_WORDLIST = "/usr/share/wordlists/dirb/common.txt"

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        wordlist = options.get("wordlist", self.DEFAULT_WORDLIST)
        cmd = [
            "gobuster", "dir",
            "-u", target.strip(),
            "-w", wordlist,
            "-q",  # quiet
            "-t", str(options.get("threads", 20)),
            "--no-error",
        ]
        extensions = options.get("extensions")
        if extensions:
            cmd.extend(["-x", extensions])
        status_codes = options.get("status_codes", "200,204,301,302,307,401,403")
        cmd.extend(["-s", status_codes])
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        results: list[dict[str, str]] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            # Gobuster output format: /path (Status: 200) [Size: 1234]
            parts = line.split()
            if parts:
                path = parts[0]
                status = ""
                size = ""
                for i, p in enumerate(parts):
                    if p.startswith("(Status:"):
                        status = parts[i + 1].rstrip(")") if i + 1 < len(parts) else ""
                    if p.startswith("[Size:"):
                        size = p.replace("[Size:", "").rstrip("]")
                results.append({"path": path, "status": status, "size": size})
        return {"results": results, "count": len(results)}
