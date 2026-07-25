"""The file_reader tool must be constrained by the same allow-list as the writer.

`FileReaderTool` is attached to `report_writer` and `post_exploit`, whose context
contains text scraped from the target under assessment — attacker-controlled by
design. It previously did a bare `Path(file_path).read_text()`, so an injected
instruction could read `/proc/self/environ` or the Django settings and echo the
contents into the report. Exfiltration needs no restart, so this is at least as
severe as the write-side hole.

The tool module itself imports `crewai`, which is absent from this Django-less
suite, so these tests pin the guard at the layer that decides: the validator the
tool now calls, plus a source-level assertion that it really calls it.
"""
import ast
import importlib.util
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent
_SAFETY = _BACKEND / "redweaver_engine" / "tools" / "file_io" / "safety.py"
_READER = _BACKEND / "redweaver_engine" / "tools" / "file_io" / "file_reader_tool.py"


def _load_safety():
    spec = importlib.util.spec_from_file_location("_rw_safety", _SAFETY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator(tmp_path, monkeypatch):
    monkeypatch.setenv("RW_ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    return _load_safety().PathValidator


# ── the tool actually calls the guard ──────────────────────────────────────
def test_reader_routes_every_read_through_the_validator():
    """A regression guard: comments mentioning the validator do not count."""
    tree = ast.parse(_READER.read_text(encoding="utf-8"))
    run = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_run"
    )
    body = ast.unparse(run)  # drops comments and docstring formatting
    assert "PathValidator.validate" in body, "_run must validate the path before reading"
    # The read must use the validated path, never the raw argument.
    assert "Path(validated)" in body
    assert "Path(file_path)" not in body


# ── secrets an injected prompt would go for ────────────────────────────────
@pytest.mark.parametrize("target", [
    "/proc/self/environ",
    "/app/redweaver/settings/base.py",
    "/app/apps/accounts/keys.py",
    "/app/.env",
    "/etc/passwd",
    "/root/.ssh/id_rsa",
])
def test_secret_paths_are_refused(validator, target):
    with pytest.raises(ValueError):
        validator.validate(target)


def test_traversal_out_of_the_artifacts_dir_is_refused(validator):
    with pytest.raises(ValueError):
        validator.validate("../../../etc/passwd")


# ── legitimate reads still work ────────────────────────────────────────────
def test_artifacts_the_writer_produced_stay_readable(validator, tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "report.md").write_text("# findings", encoding="utf-8")

    resolved = validator.validate("report.md")
    assert Path(resolved).read_text(encoding="utf-8") == "# findings"
