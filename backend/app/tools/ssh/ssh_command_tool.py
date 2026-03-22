"""SSH command execution tool for CrewAI agents.

Allows agents to execute commands on remote machines via SSH,
returning stdout, stderr, and exit code.
"""

from __future__ import annotations

import json
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.ssh.session_manager import SSHSessionManager


class SSHCommandInput(BaseModel):
    """Input schema for SSH command execution."""

    host: str = Field(description="Target hostname or IP address.")
    command: str = Field(description="Shell command to execute on the remote host.")
    username: str = Field(default="root", description="SSH username.")
    password: str = Field(default="", description="SSH password (if not using key auth).")
    key_path: str = Field(default="", description="Path to SSH private key file.")
    port: int = Field(default=22, description="SSH port number.")
    timeout: int = Field(default=60, description="Command execution timeout in seconds.")


class SSHCommandTool(BaseTool):
    """Execute commands on a remote host via SSH.

    Returns JSON with stdout, stderr, and exit_code.
    Credentials are never included in output.
    """

    name: str = "ssh_execute"
    description: str = (
        "Execute a shell command on a remote host via SSH. "
        "Returns stdout, stderr, and exit code as JSON. "
        "Use for reconnaissance, enumeration, privilege escalation, and post-exploitation."
    )
    args_schema: Type[BaseModel] = SSHCommandInput

    def _run(
        self,
        host: str,
        command: str,
        username: str = "root",
        password: str = "",
        key_path: str = "",
        port: int = 22,
        timeout: int = 60,
    ) -> str:
        try:
            mgr = SSHSessionManager.instance()
            client = mgr.get_or_create(
                host=host, port=port, username=username,
                password=password, key_path=key_path,
            )

            _, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()

            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")

            # Truncate large outputs
            max_chars = 10_000
            if len(stdout_text) > max_chars:
                stdout_text = stdout_text[:max_chars] + f"\n... [truncated, {len(stdout_text)} chars total]"
            if len(stderr_text) > max_chars:
                stderr_text = stderr_text[:max_chars] + f"\n... [truncated]"

            return json.dumps({
                "host": host,
                "command": command,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": exit_code,
            })

        except Exception as e:
            return json.dumps({
                "host": host,
                "command": command,
                "error": str(e),
                "status": "failed",
            })
