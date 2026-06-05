"""Ffuf directory and parameter fuzzing tool."""
from typing import Any

from redweaver_engine.tools.base import ToolCategory
from redweaver_engine.tools.cli.base_cli import BaseCLITool


class FfufTool(BaseCLITool):
    name = "ffuf_fuzz"
    description = (
        "Fuzz directories, files, or parameters on a target URL using ffuf. "
        "Target should include FUZZ keyword, e.g. 'https://example.com/FUZZ'. "
        "Options: wordlist='/path/to/list' (default: common.txt), "
        "extensions='php,html,bak,old,txt,json,conf,env,zip' to append file extensions, "
        "recursion=true with recursion_depth=N (default 1) to recurse into found dirs, "
        "mc='200,301,302' to match status codes, "
        "fc='404' to filter status codes."
    )
    category = ToolCategory.FUZZING
    binary_name = "ffuf"
    default_timeout = 300

    DEFAULT_WORDLIST = "/usr/share/wordlists/dirb/common.txt"

    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        wordlist = options.get("wordlist", self.DEFAULT_WORDLIST)
        url = target.strip()
        if "FUZZ" not in url:
            url = url.rstrip("/") + "/FUZZ"

        cmd = [
            "ffuf",
            "-u", url,
            "-w", wordlist,
            "-o", "/dev/stdout",
            "-of", "json",
            "-s",  # silent mode
            "-t", str(options.get("threads", 40)),
            "-rate", str(options.get("rate", 100)),
        ]
        # File extensions: accept "php,html" or ".php,.html"; ffuf wants leading dots.
        extensions = options.get("extensions")
        if extensions:
            exts = [
                e.strip() if e.strip().startswith(".") else "." + e.strip()
                for e in str(extensions).split(",")
                if e.strip()
            ]
            if exts:
                cmd.extend(["-e", ",".join(exts)])
        # Recursive content discovery into discovered directories.
        if options.get("recursion"):
            depth = options.get("recursion_depth", 1)
            cmd.extend(["-recursion", "-recursion-depth", str(depth)])
        mc = options.get("mc")
        if mc:
            cmd.extend(["-mc", mc])
        fc = options.get("fc", "404")
        if fc:
            cmd.extend(["-fc", fc])
        return cmd

    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> dict[str, Any]:
        import json as _json

        try:
            data = _json.loads(stdout)
        except _json.JSONDecodeError:
            return {"raw_output": stdout[:3000], "results": []}

        results_raw = data.get("results", [])
        results: list[dict[str, Any]] = []
        for r in results_raw:
            results.append({
                "url": r.get("url", ""),
                "status": r.get("status", 0),
                "length": r.get("length", 0),
                "words": r.get("words", 0),
                "lines": r.get("lines", 0),
                "input": r.get("input", {}).get("FUZZ", ""),
            })
        return {"results": results, "count": len(results)}
