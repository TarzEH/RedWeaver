"""Regression guards for the cross-tenant IDORs fixed in the hunt/session API.

These endpoints can only be exercised end-to-end with Django and a database,
which this suite deliberately runs without. What *is* decidable statically is the
property that actually broke: a caller-supplied id reaching ``.objects`` without
passing through ``apps.common.access``. Each test below pins one endpoint's body
so a future edit cannot quietly drop the scoping again — the bug class here is a
one-line regression (``filter(id=...)`` instead of ``scoped_get_or_404``), and a
one-line regression is exactly what a source guard catches.
"""
import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

HUNTS_VIEWS = BACKEND / "apps" / "hunts" / "views.py"
HUNTS_SERIALIZERS = BACKEND / "apps" / "hunts" / "serializers.py"
AGENTS_VIEWS = BACKEND / "apps" / "agents" / "views.py"


def _body(path: Path, qualname: str) -> str:
    """Normalized code of ``qualname`` ("func" or "Class.method") inside ``path``.

    Round-tripped through ``ast.unparse`` so comments are gone: a comment that
    merely *mentions* ``target_scope_q`` must not satisfy an assertion that the
    scope helper is actually called. Note this also normalizes string quoting to
    single quotes.
    """
    tree = ast.parse(path.read_text())
    parts = qualname.split(".")
    scope: list = tree.body
    node = None
    for i, name in enumerate(parts):
        wanted = (ast.ClassDef,) if i < len(parts) - 1 else (
            ast.FunctionDef, ast.AsyncFunctionDef
        )
        node = next((n for n in scope if isinstance(n, wanted) and n.name == name), None)
        assert node is not None, f"{qualname!r} not found in {path.name}"
        scope = node.body
    return ast.unparse(node)


# ── Fix 1: hunt creation resolves session_id / target_ids in scope ──────────
def test_hunt_create_scopes_the_session_and_targets():
    body = _body(HUNTS_SERIALIZERS, "HuntCreateSerializer.create")
    assert "scoped_get_or_404" in body
    assert "session_scope_q" in body and "target_scope_q" in body
    # The exact call that let an attacker attach a run to a victim's session.
    assert "Session.objects.filter" not in body


def test_hunt_create_never_falls_back_to_an_unscoped_none():
    # Silently resolving an unauthorized id to None was the other half of the
    # bug: the run was still created, just detached and unattributed.
    body = _body(HUNTS_SERIALIZERS, "HuntCreateSerializer.create")
    assert "if target_ids else None" not in body


def test_hunt_create_tolerates_a_missing_request_in_context():
    # Some code paths build the serializer without a request; reaching straight
    # for ``request.user`` there is an AttributeError -> 500.
    body = _body(HUNTS_SERIALIZERS, "HuntCreateSerializer.create")
    assert "getattr(request, 'user'" in body
    assert "request.user.is_authenticated" not in body


# ── Fix 2: link_target resolves the target in scope ────────────────────────
def test_link_target_resolves_the_target_through_the_access_scope():
    body = _body(HUNTS_VIEWS, "SessionViewSet.link_target")
    assert "scoped_get_or_404" in body and "target_scope_q" in body


def test_link_target_does_not_reparent_by_raw_id():
    # ``Target.objects.filter(id=target_id).update(session=...)`` moved any
    # target — including a stranger's — into the caller's own session.
    body = _body(HUNTS_VIEWS, "SessionViewSet.link_target")
    assert "Target.objects.filter" not in body
    assert ".update(session=" not in body


# ── Fix 3: graph topology run lookup is scoped ─────────────────────────────
def test_graph_topology_scopes_the_run_lookup():
    body = _body(AGENTS_VIEWS, "graph_topology")
    assert "run_scope_q" in body and "scoped_get_or_404" in body
    # Leaked the victim's target type and whether SSH creds were configured.
    assert "Run.objects.filter" not in body


# ── Fix 4: provider errors are scrubbed before they reach a response ───────
@pytest.mark.parametrize("path", [HUNTS_VIEWS, AGENTS_VIEWS])
def test_no_exception_text_is_returned_unscrubbed(path):
    src = path.read_text()
    assert src.count("str(exc)") == src.count("scrub_secrets(str(exc))"), (
        f"{path.name} returns raw exception text; provider 401s embed key fragments"
    )


# ── Fix 5: posture does not issue one findings query per run ───────────────
def test_session_posture_prefetches_findings():
    body = _body(HUNTS_VIEWS, "session_posture")
    assert "prefetch_related('findings')" in body
