"""SSH file download tool via SFTP."""

from __future__ import annotations

import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.ssh.session_manager import SSHSessionManager


class SSHDownloadInput(BaseModel):
    """Input schema for SFTP file download."""

    host: str = Field(description="Target hostname or IP address.")
    remote_path: str = Field(description="File path on the remote host to download.")
    local_path: str = Field(description="Local destination path.")
    username: str = Field(default="root", description="SSH username.")
    password: str = Field(default="", description="SSH password.")
    key_path: str = Field(default="", description="Path to SSH private key file.")
    port: int = Field(default=22, description="SSH port number.")


class SSHFileDownloadTool(BaseTool):
    """Download a file from a remote host via SFTP.

    Useful for retrieving flags, logs, configuration files,
    or evidence from a compromised machine.
    """

    name: str = "ssh_download"
    description: str = (
        "Download a file from a remote host via SFTP. "
        "Provide remote_path and local_path."
    )
    args_schema: Type[BaseModel] = SSHDownloadInput

    def _run(
        self,
        host: str,
        remote_path: str,
        local_path: str,
        username: str = "root",
        password: str = "",
        key_path: str = "",
        port: int = 22,
    ) -> str:
        try:
            mgr = SSHSessionManager.instance()
            client = mgr.get_or_create(
                host=host, port=port, username=username,
                password=password, key_path=key_path,
            )

            sftp = client.open_sftp()
            try:
                sftp.get(remote_path, local_path)
            finally:
                sftp.close()

            return json.dumps({
                "status": "success",
                "host": host,
                "remote_path": remote_path,
                "local_path": local_path,
                "message": f"Downloaded {host}:{remote_path} to {local_path}",
            })

        except Exception as e:
            return json.dumps({
                "status": "failed",
                "host": host,
                "error": str(e),
            })
