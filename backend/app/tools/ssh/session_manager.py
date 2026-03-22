"""SSH session manager: connection pooling and lifecycle management.

Provides a singleton that manages paramiko SSH connections across
multiple tool invocations within a single hunt run.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

import paramiko

logger = logging.getLogger(__name__)


class SSHSessionManager:
    """Thread-safe singleton managing SSH client connections.

    Connections are keyed by 'user@host:port' and reused across
    tool calls within the same hunt run. Call close_all() when
    the run completes.
    """

    _instance: SSHSessionManager | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._sessions: dict[str, paramiko.SSHClient] = {}
        self._session_lock = threading.Lock()
        self._allowed_hosts: set[str] | None = self._load_allowed_hosts()

    @classmethod
    def instance(cls) -> SSHSessionManager:
        """Return the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Close all connections and destroy the singleton."""
        if cls._instance is not None:
            cls._instance.close_all()
            cls._instance = None

    def get_or_create(
        self,
        host: str,
        port: int = 22,
        username: str = "root",
        password: str = "",
        key_path: str = "",
    ) -> paramiko.SSHClient:
        """Return an existing or new SSH connection."""
        self._check_allowed(host)

        key = f"{username}@{host}:{port}"
        with self._session_lock:
            client = self._sessions.get(key)
            if client is not None and client.get_transport() and client.get_transport().is_active():
                return client

            # Create new connection
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs: dict[str, Any] = {
                "hostname": host,
                "port": port,
                "username": username,
                "timeout": 30,
            }

            if key_path and os.path.isfile(key_path):
                connect_kwargs["key_filename"] = key_path
            elif password:
                connect_kwargs["password"] = password
            else:
                # Try default SSH key
                default_key = os.path.expanduser("~/.ssh/id_rsa")
                if os.path.isfile(default_key):
                    connect_kwargs["key_filename"] = default_key

            logger.info("SSH connecting to %s", key)
            client.connect(**connect_kwargs)
            self._sessions[key] = client
            return client

    def close_all(self) -> None:
        """Close all active SSH connections."""
        with self._session_lock:
            for key, client in self._sessions.items():
                try:
                    client.close()
                    logger.info("SSH closed: %s", key)
                except Exception as e:
                    logger.warning("Error closing SSH %s: %s", key, e)
            self._sessions.clear()

    def _check_allowed(self, host: str) -> None:
        """Validate host against allowed-hosts whitelist."""
        if self._allowed_hosts is not None and host not in self._allowed_hosts:
            raise PermissionError(
                f"SSH to '{host}' is not in the allowed hosts list. "
                f"Set SSH_ALLOWED_HOSTS env var to allow it."
            )

    @staticmethod
    def _load_allowed_hosts() -> set[str] | None:
        """Load allowed hosts from SSH_ALLOWED_HOSTS env var (comma-separated)."""
        raw = os.environ.get("SSH_ALLOWED_HOSTS", "").strip()
        if not raw:
            return None  # No whitelist = allow all
        return {h.strip() for h in raw.split(",") if h.strip()}
