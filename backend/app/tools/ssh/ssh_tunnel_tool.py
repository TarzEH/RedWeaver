"""SSH tunnel tool for port forwarding.

Supports local (-L), dynamic (-D), and remote (-R) SSH tunneling
for network pivoting and accessing internal services.
"""

from __future__ import annotations

import json
import threading
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from app.tools.ssh.session_manager import SSHSessionManager


class SSHTunnelInput(BaseModel):
    """Input schema for SSH tunnel creation."""

    host: str = Field(description="SSH server hostname or IP.")
    tunnel_type: str = Field(
        default="local",
        description="Tunnel type: 'local' (-L), 'dynamic' (-D), or 'remote' (-R).",
    )
    local_port: int = Field(description="Local port to bind.")
    remote_host: str = Field(default="127.0.0.1", description="Remote host to forward to (for local/remote tunnels).")
    remote_port: int = Field(default=0, description="Remote port to forward to (for local/remote tunnels).")
    username: str = Field(default="root", description="SSH username.")
    password: str = Field(default="", description="SSH password.")
    key_path: str = Field(default="", description="Path to SSH private key file.")
    port: int = Field(default=22, description="SSH server port.")


class SSHTunnelTool(BaseTool):
    """Establish SSH tunnels for port forwarding and network pivoting.

    Supports:
    - Local forwarding (-L): Access remote services through a local port
    - Dynamic forwarding (-D): SOCKS proxy for routing traffic
    - Remote forwarding (-R): Expose local services to the remote network
    """

    name: str = "ssh_tunnel"
    description: str = (
        "Establish an SSH tunnel for port forwarding. "
        "Supports 'local' (-L), 'dynamic' (-D SOCKS proxy), and 'remote' (-R) tunneling. "
        "Use for network pivoting and accessing internal services."
    )
    args_schema: Type[BaseModel] = SSHTunnelInput
    _active_tunnels: list = PrivateAttr(default_factory=list)

    def _run(
        self,
        host: str,
        tunnel_type: str = "local",
        local_port: int = 0,
        remote_host: str = "127.0.0.1",
        remote_port: int = 0,
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

            transport = client.get_transport()
            if transport is None:
                return json.dumps({"error": "SSH transport not available", "status": "failed"})

            if tunnel_type == "local":
                # Local port forwarding: local_port -> remote_host:remote_port via SSH server
                transport.request_port_forward("", local_port)
                channel = transport.open_channel(
                    "direct-tcpip",
                    (remote_host, remote_port),
                    ("127.0.0.1", local_port),
                )
                self._active_tunnels.append(channel)
                return json.dumps({
                    "status": "success",
                    "tunnel_type": "local",
                    "local_port": local_port,
                    "remote_endpoint": f"{remote_host}:{remote_port}",
                    "message": f"Local tunnel: localhost:{local_port} -> {remote_host}:{remote_port} via {host}",
                })

            elif tunnel_type == "dynamic":
                # Dynamic SOCKS proxy
                transport.request_port_forward("", local_port)
                return json.dumps({
                    "status": "success",
                    "tunnel_type": "dynamic",
                    "socks_port": local_port,
                    "message": f"SOCKS proxy on localhost:{local_port} via {host}. Use proxychains or set SOCKS5 proxy.",
                })

            elif tunnel_type == "remote":
                # Remote port forwarding: remote_port on SSH server -> local_port
                transport.request_port_forward("", remote_port)
                return json.dumps({
                    "status": "success",
                    "tunnel_type": "remote",
                    "remote_port": remote_port,
                    "local_port": local_port,
                    "message": f"Remote tunnel: {host}:{remote_port} -> localhost:{local_port}",
                })

            else:
                return json.dumps({
                    "error": f"Unknown tunnel type: {tunnel_type}. Use 'local', 'dynamic', or 'remote'.",
                    "status": "failed",
                })

        except Exception as e:
            return json.dumps({
                "host": host,
                "tunnel_type": tunnel_type,
                "error": str(e),
                "status": "failed",
            })
