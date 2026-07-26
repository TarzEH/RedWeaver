"""Run-creation endpoint: validate fields -> create Run -> enqueue Celery.

Historically this was a "chat" endpoint: it ran a regex over free text to guess
a target, then answered with a hardcoded sentence pretending to be an assistant.
There was never a model behind it, and the regex could *reject* a perfectly
valid target ("example.com" with no scan verb parsed to nothing), so the UI now
posts the three fields the parser could actually recover — target, objective and
scope — as a form.

The path stays ``/api/chat`` because that is what clients already POST to. It is
not switched to ``POST /api/hunts``: ``HuntCreateSerializer`` only derives
``Run.target`` from a ``Target`` row named by ``target_ids``, so a free-text
target (a URL typed by an operator, with no Target object behind it) would
create a run with an empty target there.
"""
import uuid

from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.access import scoped_get_or_404, session_scope_q

from .budget import parse_budget_usd
from .models import Run, Session

# The objectives the pipeline actually distinguishes. Anything else is a typo
# or a stale client, and silently running a "comprehensive" hunt under another
# name would misreport what was done.
OBJECTIVES = ("comprehensive", "quick", "stealth")
DEFAULT_OBJECTIVE = "comprehensive"


def normalize_objective(value) -> str:
    """Coerce a client-supplied objective to a supported one.

    Unrecognised/blank values fall back to the default rather than 400-ing: the
    objective is a mode selector, not the point of the request.
    """
    candidate = str(value or "").strip().lower()
    return candidate if candidate in OBJECTIVES else DEFAULT_OBJECTIVE


def _as_uuid(value) -> uuid.UUID:
    """Coerce a client-supplied session id to a UUID, 400-ing on garbage.

    The body is free-form JSON, so ``session_id`` can be any type. Handing a
    non-UUID straight to the UUID column raises deep in the driver — a 500 where
    a 400 belongs. ``HuntCreateSerializer`` gets this from its ``UUIDField``;
    this endpoint has no serializer, so it does the same check by hand.
    """
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        raise ValidationError({"session_id": "Not a valid UUID."}) from None


def _attack_techniques(raw) -> list[str]:
    """Normalize ATT&CK technique ids (e.g. "t1190" -> "T1190"), dropping junk.

    Best-effort: the engine import is optional, so a build without it still
    starts hunts (just without an ATT&CK focus) instead of failing the request.
    """
    if not isinstance(raw, (list, tuple)):
        return []
    try:
        from redweaver_engine.crews.bug_hunt.attack_planning import normalize_technique_id
    except Exception:
        return []
    seen: list[str] = []
    for item in raw:
        normalized = normalize_technique_id(item)
        if normalized and normalized not in seen:
            seen.append(normalized)
    return seen


class ChatView(APIView):
    """POST /api/chat — create a hunt run from explicit fields and enqueue it."""

    def post(self, request):
        body = request.data or {}
        # `message`/`input`/`text` are legacy aliases carrying a bare target.
        # Taken verbatim — no parsing, so nothing can be rejected as "not a scan".
        target = str(
            body.get("target")
            or body.get("message")
            or body.get("input")
            or body.get("text")
            or ""
        ).strip()

        if not target:
            return Response(
                {"detail": "A target is required (URL, domain, or IP)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Same rule as ``HuntCreateSerializer.create``: the caller names the
        # session by id, so the lookup must go through the access scope. An
        # unscoped ``Session.objects.filter(id=...)`` let any authenticated user
        # plant a run inside a stranger's session — inheriting their workspace —
        # and then run a real scan attributed to that tenant. An id outside the
        # caller's scope must 404, never fall through to an unscoped run.
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            user = None

        session = None
        if body.get("session_id"):
            if user is None:
                raise PermissionDenied("Authentication is required to reference a session.")
            session = scoped_get_or_404(
                Session, user, session_scope_q, id=_as_uuid(body["session_id"])
            )

        run = Run.objects.create(
            session=session,
            workspace=(session.workspace if session else None),
            created_by=user,
            target=target,
            scope=str(body.get("scope") or "").strip(),
            objective=normalize_objective(body.get("objective")),
            attack_focus=_attack_techniques(body.get("attack_techniques")),
            budget_usd=parse_budget_usd(body.get("budget_usd")),
            ssh_config=body.get("ssh_config"),
        )

        try:
            from .views import _enqueue_run
            _enqueue_run(run)  # apply_async with soft timeout + records task id
        except Exception:
            pass

        # No `reply`: there is no assistant here, and the caller renders the run
        # itself. `created_run`/`deferred` are kept for older clients.
        return Response(
            {
                "run_id": str(run.id),
                "status": run.status,
                "created_run": True,
                "deferred": True,
            },
            status=status.HTTP_201_CREATED,
        )
