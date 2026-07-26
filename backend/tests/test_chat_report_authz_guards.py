"""Regression guards for the two entry points ``test_api_authz_guards`` misses.

``apps/hunts/chat_views.py`` (POST /api/chat) creates a Run from a caller-named
``session_id``, exactly like ``HuntCreateSerializer.create`` — and carried the
same cross-tenant IDOR after that one was fixed. ``apps/reports/views.py`` was
the last view module returning raw exception text to a client.

Same technique as ``test_api_authz_guards``: the suite runs without Django and
without a database, so the endpoints cannot be exercised end-to-end. What is
decidable statically is the property that broke — a caller-supplied id reaching
``.objects`` without ``apps.common.access``, and an exception object reaching a
response body without ``scrub_secrets``. Bodies are round-tripped through
``ast.unparse``, so a comment naming a helper cannot satisfy an assertion.
"""
import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

CHAT_VIEWS = BACKEND / "apps" / "hunts" / "chat_views.py"
REPORTS_VIEWS = BACKEND / "apps" / "reports" / "views.py"


def _body(path: Path, qualname: str) -> str:
    """Normalized code of ``qualname`` ("func" or "Class.method") inside ``path``.

    Comments are stripped by the round-trip, and string quoting is normalized to
    single quotes — assertions below must be written accordingly.
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


def _raw_exception_interpolations(path: Path) -> list[str]:
    """f-strings in ``path`` that interpolate a caught exception unscrubbed.

    Catches the shape the count-based guard cannot see: ``f"failed: {exc}"``
    contains neither ``str(exc)`` nor ``scrub_secrets``, so a naive count of
    ``str(exc)`` reads it as clean. ``str(exc)`` is unwrapped first so
    ``{str(exc)}`` is treated the same as ``{exc}``; a ``{scrub_secrets(...)}``
    wrapper is not unwrapped and therefore not reported.
    """
    tree = ast.parse(path.read_text())
    caught = {
        h.name for h in ast.walk(tree)
        if isinstance(h, ast.ExceptHandler) and h.name
    }
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            expr = part.value
            if (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Name)
                and expr.func.id == "str"
                and expr.args
            ):
                expr = expr.args[0]
            if isinstance(expr, ast.Name) and expr.id in caught:
                offenders.append(ast.unparse(node))
    return offenders


# ── Fix 1: POST /api/chat resolves session_id in scope ─────────────────────
def test_chat_run_creation_scopes_the_session():
    # The exact hole: `Session.objects.filter(id=body["session_id"]).first()`
    # let any authenticated user attach a run to a stranger's session, inherit
    # `session.workspace`, and start a real scan attributed to that tenant.
    body = _body(CHAT_VIEWS, "ChatView.post")
    assert "scoped_get_or_404" in body and "session_scope_q" in body
    assert "Session.objects" not in body


def test_chat_run_creation_never_falls_back_to_an_unscoped_session():
    # An id outside the caller's scope must raise (404/403), not resolve to
    # None: a None session would still create the run, just detached.
    body = _body(CHAT_VIEWS, "ChatView.post")
    assert ".filter(" not in body
    assert ".first()" not in body


def test_chat_run_creation_tolerates_an_absent_or_anonymous_user():
    # `request.user.is_authenticated` is an AttributeError -> 500 when no auth
    # middleware ran; and an AnonymousUser must not reach the scope helper.
    body = _body(CHAT_VIEWS, "ChatView.post")
    assert "getattr(request, 'user'" in body
    assert "request.user.is_authenticated" not in body
    assert "getattr(user, 'is_authenticated'" in body


def test_chat_run_creation_rejects_a_malformed_session_id():
    # A non-UUID body value reaching the UUID column is a 500 where a 4xx
    # belongs. HuntCreateSerializer gets this from its UUIDField.
    body = _body(CHAT_VIEWS, "ChatView.post")
    assert "_as_uuid" in body

    helper = _body(CHAT_VIEWS, "_as_uuid")
    assert "uuid.UUID" in helper
    assert "ValueError" in helper and "TypeError" in helper
    assert "ValidationError" in helper


def test_chat_run_creation_still_builds_the_whole_run():
    # The scoping fix must not quietly drop fields the endpoint owns; each of
    # these is the only place the value reaches the Run.
    body = _body(CHAT_VIEWS, "ChatView.post")
    for expected in (
        "normalize_objective(",
        "parse_budget_usd(",
        "_attack_techniques(",
        "attack_focus=",
        "ssh_config=",
        "scope=",
        "workspace=",
        "'run_id'",
    ):
        assert expected in body, f"chat run creation lost {expected!r}"


# ── Fix 2: provider errors are scrubbed before they reach a response ───────
@pytest.mark.parametrize("path", [REPORTS_VIEWS, CHAT_VIEWS])
def test_no_exception_text_is_returned_unscrubbed(path):
    src = path.read_text()
    assert src.count("str(exc)") == src.count("scrub_secrets(str(exc))"), (
        f"{path.name} returns raw exception text; provider 401s embed key fragments"
    )


@pytest.mark.parametrize("path", [REPORTS_VIEWS, CHAT_VIEWS])
def test_no_exception_object_is_interpolated_into_a_message(path):
    offenders = _raw_exception_interpolations(path)
    assert not offenders, (
        f"{path.name} interpolates a caught exception unscrubbed: {offenders}"
    )


def test_report_html_export_scrubs_its_render_error():
    # The HTML export resolves a model name through the LLM factory, so a
    # provider 401 (partial API key in the body) can surface here.
    body = _body(REPORTS_VIEWS, "run_report_export")
    assert "scrub_secrets(str(exc))" in body


def test_reports_views_imports_the_scrubber():
    assert "from apps.common.redaction import scrub_secrets" in REPORTS_VIEWS.read_text()
