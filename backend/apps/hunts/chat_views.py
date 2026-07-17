"""Unified chat endpoint: parse intent -> create Run -> enqueue Celery."""
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Run, Session
from .scan_intent import ScanIntentParser

_parser = ScanIntentParser()


class ChatView(APIView):
    """POST /api/chat — natural-language entry point for starting a hunt."""

    def post(self, request):
        body = request.data or {}
        message = body.get("message") or body.get("input") or body.get("text") or ""
        explicit_target = (body.get("target") or "").strip()
        objective = body.get("objective") or "comprehensive"

        target = explicit_target
        if not target:
            intent = _parser.parse(message)
            if intent:
                target = intent.target
                objective = intent.objective

        if not target:
            return Response({
                "reply": "Tell me a target to assess — paste a URL, domain, or IP "
                         "(e.g. `scan https://example.com`).",
                "deferred": False,
                "created_run": False,
            })

        session = None
        if body.get("session_id"):
            session = Session.objects.filter(id=body["session_id"]).first()

        run = Run.objects.create(
            session=session,
            workspace=(session.workspace if session else None),
            created_by=(request.user if request.user.is_authenticated else None),
            target=target,
            scope=body.get("scope") or "",
            objective=objective,
            ssh_config=body.get("ssh_config"),
        )

        try:
            from .views import _enqueue_run
            _enqueue_run(run)  # apply_async with soft timeout + records task id
        except Exception:
            pass

        return Response({
            "reply": f"Starting a {objective} assessment of {target}. "
                     f"Watch the agents work in real time.",
            "deferred": True,
            "created_run": True,
            "run_id": str(run.id),
        })
