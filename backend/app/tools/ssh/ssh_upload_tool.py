"""SSH file upload tool via SFTP."""

from __future__ import annotations

import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.ssh.session_manager import SSHSessionManager


class SSHUploadInput(BaseModel):
    """Input schema for SFTP file upload."""

    host: str = Field(description="Target hostname or IP address.")
    local_path: str = Field(description="Local file path to upload.")
    remote_path: str = Field(description="Destination path on the remote host.")
    username: str = Field(default="root", description="SSH username.")
    password: str = Field(default="", description="SSH password.")
    key_path: str = Field(default="", description="Path to SSH private key file.")
    port: int = Field(default=22, description="SSH port number.")


class SSHFileUploadTool(BaseTool):
    """Upload a file to a remote host via SFTP.

    Useful for deploying scripts, payloads, or enumeration tools
    to a compromised machine.
    """

    name: str = "ssh_upload"
    description: str = (
        "Upload a local file to a remote host via SFTP. "
        "Provide local_path and remote_path."
    )
    args_schema: Type[BaseModel] = SSHUploadInput

    def _run(
        self,
        host: str,
        local_path: str,
        remote_path: str,
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
                sftp.put(local_path, remote_path)
            finally:
                sftp.close()

            return json.dumps({
                "status": "success",
                "host": host,
                "local_path": local_path,
                "remote_path": remote_path,
                "message": f"Uploaded {local_path} to {host}:{remote_path}",
            })

        except Exception as e:
            return json.dumps({
                "status": "failed",
                "host": host,
                "error": str(e),
            })
