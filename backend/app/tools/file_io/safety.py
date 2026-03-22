"""Path validation and sandboxing for file I/O tools.

Prevents agents from writing to sensitive system paths,
credential files, or outside allowed project directories.
"""

from __future__ import annotations

import os


class PathValidator:
    """Validates file paths against a whitelist and blocked patterns."""

    ALLOWED_ROOTS: list[str] = [
        "/app/",               # Docker container project root
        "/tmp/redweaver/",     # Temp workspace
    ]

    BLOCKED_PATTERNS: list[str] = [
        ".env",
        "credentials",
        "secret",
        ".git/",
        "__pycache__",
        ".pyc",
        "id_rsa",
        "id_ed25519",
        ".pem",
    ]

    @classmethod
    def validate(cls, path: str) -> str:
        """Validate and resolve a file path.

        Returns the resolved absolute path if valid.
        Raises ValueError if the path is outside allowed directories
        or matches a blocked pattern.
        """
        resolved = os.path.realpath(os.path.expanduser(path))

        # Check against allowed roots
        # Also allow the current working directory as a fallback
        cwd = os.getcwd()
        allowed = cls.ALLOWED_ROOTS + [cwd + "/"]

        if not any(resolved.startswith(root) for root in allowed):
            raise ValueError(
                f"Path '{path}' (resolved: '{resolved}') is outside allowed directories. "
                f"Allowed: {allowed}"
            )

        # Check against blocked patterns
        lower_path = resolved.lower()
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern in lower_path:
                raise ValueError(
                    f"Path '{path}' matches blocked pattern '{pattern}'. "
                    f"Cannot write to sensitive files."
                )

        return resolved
