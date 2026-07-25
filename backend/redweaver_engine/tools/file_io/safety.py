"""Path validation and sandboxing for file I/O tools.

The agents that carry ``file_writer`` (``report_writer``, ``post_exploit``) work
on context scraped from the *target* being scanned, which is attacker-controlled
by design. A prompt injected into a crawled page ("before writing the report,
use file_writer to write ... to /app/apps/hunts/tasks.py") therefore has to be
harmless at the filesystem layer — the LLM cannot be trusted to refuse it.

``/app`` is the container's **code root** (the Dockerfile copies ``redweaver/``,
``redweaver_engine/``, ``apps/`` and ``manage.py`` there and sets
``WORKDIR /app``), so allowing writes anywhere under ``/app`` — or under the
process CWD, which *is* ``/app`` — meant an injected instruction could rewrite
the application's own source. The Celery worker re-imports that source on its
next restart, holding the DB credentials and every user's decrypted API keys.

So writes are confined to two *data* directories that contain no importable
code:

* the artifacts directory — ``$RW_ARTIFACTS_DIR``, else ``$MEDIA_ROOT/artifacts``,
  else ``/app/media/artifacts`` (``/app/media`` already exists in the image);
* ``/tmp/redweaver/`` — the scratch workspace.

Containment is enforced on the **fully resolved real path**, so ``..`` segments,
``~`` expansion and symlinks are all normalised away *before* the check.
``BLOCKED_PATTERNS`` is kept as a second, independent layer — it is not the
primary control.
"""

from __future__ import annotations

import os

#: Env var that overrides the artifacts directory outright.
ARTIFACTS_DIR_ENV = "RW_ARTIFACTS_DIR"
#: Django's ``MEDIA_ROOT`` (read from the environment so this module stays
#: importable without Django — it is plain Python and directly unit-testable).
MEDIA_ROOT_ENV = "MEDIA_ROOT"
DEFAULT_MEDIA_ROOT = "/app/media"
ARTIFACTS_SUBDIR = "artifacts"
#: Scratch workspace outside the code root.
TMP_WORKSPACE = "/tmp/redweaver"


def _real(path: str) -> str:
    """``realpath`` without a trailing separator (``/`` normalises to ``/``)."""
    resolved = os.path.realpath(os.path.expanduser(path))
    return resolved.rstrip(os.sep) or os.sep


def _is_within(resolved: str, root: str) -> bool:
    """True if ``resolved`` is ``root`` itself or lives underneath it.

    Compares whole path components, so ``/app/media/artifacts-evil`` does not
    pass as being inside ``/app/media/artifacts``.
    """
    if resolved == root:
        return True
    return resolved.startswith(root.rstrip(os.sep) + os.sep)


class PathValidator:
    """Validates file paths against an allow-list of data directories.

    The allow-list deliberately excludes the application source tree and the
    process working directory.
    """

    BLOCKED_PATTERNS: list[str] = [
        ".env",
        "credentials",
        "secret",
        ".git/",
        "__pycache__",
        ".pyc",
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        "id_dsa",
        ".pem",
        ".ssh/",
        "authorized_keys",
        "known_hosts",
        ".htpasswd",
        ".netrc",
    ]

    # ── allowed roots ──────────────────────────────────────────────────────

    @classmethod
    def artifacts_dir(cls) -> str:
        """Resolved absolute path of the agent artifacts directory."""
        override = os.environ.get(ARTIFACTS_DIR_ENV, "").strip()
        if override:
            return _real(override)
        media_root = os.environ.get(MEDIA_ROOT_ENV, "").strip() or DEFAULT_MEDIA_ROOT
        return _real(os.path.join(media_root, ARTIFACTS_SUBDIR))

    @classmethod
    def allowed_roots(cls) -> list[str]:
        """The only directories agents may write into, fully resolved.

        Resolved every call rather than cached at import: the roots are
        environment-derived, and ``realpath`` matters because ``/tmp`` is a
        symlink on some platforms (macOS → ``/private/tmp``).
        """
        roots = [cls.artifacts_dir(), _real(TMP_WORKSPACE)]
        return list(dict.fromkeys(roots))

    @classmethod
    def ensure_artifacts_dir(cls) -> str:
        """Create the artifacts directory if missing and return it.

        ``FileWriterTool`` already ``makedirs``es the parent of the validated
        path, so this is a convenience for callers that want the directory up
        front (e.g. to hand an agent a concrete output path).
        """
        path = cls.artifacts_dir()
        os.makedirs(path, exist_ok=True)
        return path

    # ── validation ─────────────────────────────────────────────────────────

    @classmethod
    def validate(cls, path: str) -> str:
        """Validate and resolve a file path for writing.

        Returns the resolved absolute path if valid. Raises ``ValueError`` if
        the path escapes the allowed roots or matches a blocked pattern.

        A *relative* path is interpreted against the artifacts directory (not
        the process CWD, which is the code root) so agents emitting a bare
        filename keep working.
        """
        if not isinstance(path, str) or not path.strip():
            raise ValueError("Path must be a non-empty string.")
        if "\x00" in path:
            raise ValueError("Path contains a NUL byte.")

        candidate = os.path.expanduser(path.strip())
        if not os.path.isabs(candidate):
            # Anchor bare/relative names to the artifacts dir, never to CWD.
            candidate = os.path.join(cls.artifacts_dir(), candidate)

        # realpath collapses "..", "." and follows symlinks, so containment is
        # checked against what the write will *actually* touch.
        resolved = _real(candidate)

        roots = cls.allowed_roots()
        if not any(_is_within(resolved, root) for root in roots):
            raise ValueError(
                f"Path '{path}' (resolved: '{resolved}') is outside the allowed "
                f"directories. Allowed: {roots}"
            )

        # Second, independent layer — never the only thing standing in the way.
        lower_path = resolved.lower()
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern in lower_path:
                raise ValueError(
                    f"Path '{path}' matches blocked pattern '{pattern}'. "
                    f"Cannot write to sensitive files."
                )

        return resolved
