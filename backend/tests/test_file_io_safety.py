"""Unit tests for the file-writer path sandbox (no Django, no DB).

The bug these guard against is a prompt-injection → RCE chain: ``file_writer`` is
attached to ``report_writer`` / ``post_exploit``, whose context contains text
scraped from the *target* being scanned. ``/app`` is the container's code root,
so an allow-list of ``/app/`` (plus a CWD fallback that also resolved to
``/app``) let an injected instruction rewrite the application's own source —
which the Celery worker, holding the DB credentials and every user's decrypted
API keys, re-imports on its next restart.
"""
import importlib.util
import os
import pathlib

import pytest

# safety.py is deliberately pure Python (stdlib only) so it can be tested
# without Django or a DB. Its *package* __init__ pulls in the CrewAI tool
# classes, which aren't installed in this suite — so load the module by path.
_SAFETY = (
    pathlib.Path(__file__).resolve().parents[1]
    / "redweaver_engine" / "tools" / "file_io" / "safety.py"
)
_spec = importlib.util.spec_from_file_location("rw_file_io_safety", _SAFETY)
_safety = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_safety)

PathValidator = _safety.PathValidator


@pytest.fixture(autouse=True)
def _clean_artifacts_env(monkeypatch):
    """Ambient RW_ARTIFACTS_DIR / MEDIA_ROOT would move the allow-list."""
    monkeypatch.delenv("RW_ARTIFACTS_DIR", raising=False)
    monkeypatch.delenv("MEDIA_ROOT", raising=False)


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    """A real, writable artifacts dir on disk (needed for the symlink tests)."""
    d = tmp_path / "media" / "artifacts"
    d.mkdir(parents=True)
    monkeypatch.setenv("RW_ARTIFACTS_DIR", str(d))
    return d


# ── the attack ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "target",
    [
        "/app/apps/hunts/tasks.py",              # the Celery task the worker imports
        "/app/manage.py",
        "/app/redweaver/settings/base.py",
        "/app/redweaver_engine/tools/file_io/safety.py",  # the sandbox itself
        "/app/apps/accounts/models.py",
        "/app/entrypoint.sh",
    ],
)
def test_application_source_cannot_be_overwritten(target):
    with pytest.raises(ValueError):
        PathValidator.validate(target)


def test_app_root_is_not_wholesale_allowed():
    # /app is the code root; only the media/artifacts subtree is writable.
    with pytest.raises(ValueError):
        PathValidator.validate("/app/pwned.py")
    with pytest.raises(ValueError):
        PathValidator.validate("/app/media/../apps/hunts/tasks.py")


def test_cwd_is_not_a_fallback_root(tmp_path, monkeypatch):
    # The old validator whitelisted os.getcwd() — which in the container IS /app.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        PathValidator.validate(str(tmp_path / "evil.py"))


# ── traversal / symlink / normalisation ────────────────────────────────────
@pytest.mark.parametrize(
    "target",
    [
        "/app/media/artifacts/../../apps/hunts/tasks.py",
        "/app/media/artifacts/../../../etc/passwd",
        "/app/media/artifacts/./../../manage.py",
        "../../../../etc/passwd",          # relative traversal out of artifacts
        "..",
        "/etc/passwd",
        "/root/.ssh/authorized_keys",
        "~/.bashrc",                        # ~ expands outside the roots
    ],
)
def test_traversal_and_absolute_escapes_are_rejected(target):
    with pytest.raises(ValueError):
        PathValidator.validate(target)


def test_symlink_out_of_the_artifacts_dir_is_rejected(artifacts, tmp_path):
    outside = tmp_path / "code"
    outside.mkdir()
    (artifacts / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        PathValidator.validate(str(artifacts / "escape" / "tasks.py"))


def test_sibling_directory_sharing_a_prefix_is_rejected():
    # startswith() on a bare prefix would let /app/media/artifacts-evil through.
    with pytest.raises(ValueError):
        PathValidator.validate("/app/media/artifacts-evil/x.md")
    with pytest.raises(ValueError):
        PathValidator.validate("/tmp/redweaver-evil/x.md")


@pytest.mark.parametrize("target", ["", "   ", "\x00/app/media/artifacts/a.md"])
def test_malformed_paths_are_rejected(target):
    with pytest.raises(ValueError):
        PathValidator.validate(target)


# ── the legitimate paths still work ────────────────────────────────────────
def test_artifacts_path_is_allowed():
    out = PathValidator.validate("/app/media/artifacts/report.md")
    assert out == "/app/media/artifacts/report.md"


def test_nested_artifacts_path_is_allowed():
    out = PathValidator.validate("/app/media/artifacts/run-123/loot/creds.txt")
    assert out.startswith("/app/media/artifacts/")


def test_tmp_workspace_is_allowed():
    # /tmp is a symlink on macOS, so compare against the resolved form.
    assert PathValidator.validate("/tmp/redweaver/scratch.md") == os.path.realpath(
        "/tmp/redweaver/scratch.md"
    )


def test_relative_path_is_anchored_to_artifacts_not_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert PathValidator.validate("report.md") == "/app/media/artifacts/report.md"


def test_artifacts_dir_follows_env_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "m"))
    assert PathValidator.artifacts_dir() == os.path.realpath(str(tmp_path / "m" / "artifacts"))

    monkeypatch.setenv("RW_ARTIFACTS_DIR", str(tmp_path / "custom"))
    assert PathValidator.artifacts_dir() == os.path.realpath(str(tmp_path / "custom"))
    # …and the override becomes the allowed root.
    assert PathValidator.validate(str(tmp_path / "custom" / "a.md")).endswith("custom/a.md")


def test_ensure_artifacts_dir_creates_it(monkeypatch, tmp_path):
    target = tmp_path / "media" / "artifacts"
    monkeypatch.setenv("RW_ARTIFACTS_DIR", str(target))
    assert not target.exists()
    created = PathValidator.ensure_artifacts_dir()
    assert os.path.isdir(created)
    PathValidator.ensure_artifacts_dir()  # idempotent


# ── blocked patterns remain as a second layer ──────────────────────────────
@pytest.mark.parametrize(
    "name",
    [".env", "aws_credentials.txt", "my_secret.md", "id_rsa", "server.pem",
     "authorized_keys", ".netrc", "cached.pyc"],
)
def test_sensitive_names_blocked_even_inside_an_allowed_root(name):
    with pytest.raises(ValueError, match="blocked pattern"):
        PathValidator.validate(f"/app/media/artifacts/{name}")


def test_allowed_roots_exclude_the_code_root():
    roots = PathValidator.allowed_roots()
    assert "/app" not in roots and "/app/" not in roots
    assert any(r.endswith("/artifacts") for r in roots)
    assert os.path.realpath("/tmp/redweaver") in roots
