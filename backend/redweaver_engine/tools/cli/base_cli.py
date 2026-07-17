"""Base class for CLI security tools executed via subprocess."""
import asyncio
import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from redweaver_engine.tools.base import ToolCategory
from redweaver_engine.tools.instrumentation import CLIRaw, stash_cli_raw


class BaseCLITool(ABC):
    """Abstract base for all CLI security tools.

    Subclasses implement ``build_command`` and ``parse_output`` to wrap
    a specific binary. The base handles subprocess execution, timeouts,
    error handling, and availability checks.
    """

    name: str
    description: str
    category: ToolCategory
    binary_name: str
    default_timeout: int = 300  # 5 minutes

    # ------------------------------------------------------------------ #
    # Availability
    # ------------------------------------------------------------------ #

    def is_available(self) -> bool:
        """Return True if the binary is on $PATH."""
        return shutil.which(self.binary_name) is not None

    # ------------------------------------------------------------------ #
    # Abstract methods for subclasses
    # ------------------------------------------------------------------ #

    @abstractmethod
    def build_command(
        self, target: str, scope: str, options: dict[str, Any]
    ) -> list[str]:
        """Build the CLI command as a list of arguments."""
        ...

    @abstractmethod
    def parse_output(
        self, stdout: str, stderr: str, return_code: int
    ) -> str | dict[str, Any]:
        """Parse tool stdout/stderr into structured results."""
        ...

    # ------------------------------------------------------------------ #
    # Synchronous execution
    # ------------------------------------------------------------------ #

    def run(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        options = options or {}
        if not self.is_available():
            return {"error": f"{self.binary_name} not found on PATH", "available": False}

        cmd = self.build_command(target, scope, options)
        timeout = options.get("timeout", self.default_timeout)

        cmd_str = " ".join(str(c) for c in cmd)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/tmp",
            )
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd),
                stdout=result.stdout, stderr=result.stderr,
                exit_code=result.returncode,
            ))
            return self.parse_output(result.stdout, result.stderr, result.returncode)
        except subprocess.TimeoutExpired:
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd),
                stderr=f"timed out after {timeout}s", exit_code=-1,
            ))
            return {"error": f"{self.binary_name} timed out after {timeout}s"}
        except Exception as e:
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd), stderr=str(e), exit_code=-2,
            ))
            return {"error": f"{self.binary_name} failed: {e!s}"}

    # ------------------------------------------------------------------ #
    # Async execution
    # ------------------------------------------------------------------ #

    async def arun(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        options = options or {}
        if not self.is_available():
            return {"error": f"{self.binary_name} not found on PATH", "available": False}

        cmd = self.build_command(target, scope, options)
        timeout = options.get("timeout", self.default_timeout)

        cmd_str = " ".join(str(c) for c in cmd)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd="/tmp",
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            out = stdout_bytes.decode(errors="replace")
            err = stderr_bytes.decode(errors="replace")
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd),
                stdout=out, stderr=err, exit_code=proc.returncode or 0,
            ))
            return self.parse_output(out, err, proc.returncode or 0)
        except asyncio.TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd),
                stderr=f"timed out after {timeout}s", exit_code=-1,
            ))
            return {"error": f"{self.binary_name} timed out after {timeout}s"}
        except Exception as e:
            stash_cli_raw(CLIRaw(
                command=cmd_str, argv=list(cmd), stderr=str(e), exit_code=-2,
            ))
            return {"error": f"{self.binary_name} failed: {e!s}"}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe_json_lines(stdout: str) -> list[dict[str, Any]]:
        """Parse newline-delimited JSON (JSONL) output, skipping bad lines."""
        results: list[dict[str, Any]] = []
        for line in stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results

    def __repr__(self) -> str:
        avail = "available" if self.is_available() else "missing"
        return f"<{self.__class__.__name__} binary={self.binary_name} [{avail}]>"
