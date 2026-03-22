"""Unified chat: same deep agent for all messages; optional run creation on scan intent."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from app.models.chat import ChatRequest, ChatResult
from app.models.run import Run, GraphState
from app.repositories.api_keys_repository import ApiKeysRepositoryProtocol
from app.repositories.run_repository import RunRepositoryProtocol
from app.services.scan_intent_parser import ScanIntentParser

_intent_parser = ScanIntentParser()


def _last_assistant_content(result: dict[str, Any]) -> str:
    """Extract last assistant message content from agent result for chat reply."""
    messages = result.get("messages") or []
    for m in reversed(messages):
        if isinstance(m, dict):
            if m.get("role") == "assistant":
                return (m.get("content") or "").strip()
        else:
            role = getattr(m, "type", None) or getattr(m, "role", "")
            if role in ("ai", "assistant"):
                content = getattr(m, "content", None) or ""
                if isinstance(content, list):
                    content = " ".join(getattr(p, "text", str(p)) for p in content)
                return (str(content) or "").strip()
    return ""


def _result_messages_to_dicts(messages: Any) -> list[dict]:
    """Convert agent result messages to list[dict] for run storage."""
    out: list[dict] = []
    for m in messages or []:
        if isinstance(m, dict):
            out.append({"role": m.get("role", "assistant"), "content": m.get("content", "") or ""})
            continue
        role = getattr(m, "type", None) or getattr(m, "role", "assistant")
        if role == "human":
            role = "user"
        elif role == "ai":
            role = "assistant"
        content = getattr(m, "content", None) or ""
        if isinstance(content, list):
            content = " ".join(getattr(part, "text", str(part)) for part in content)
        out.append({"role": role, "content": str(content) if content else ""})
    return out


class ChatService:
    """Chat service: creates runs on scan intent and triggers the hunt workflow."""

    def __init__(
        self,
        run_repository: RunRepositoryProtocol,
        api_keys_repository: ApiKeysRepositoryProtocol,
        hunt_graph: Any = None,
    ) -> None:
        self._runs = run_repository
        self._keys = api_keys_repository
        self._hunt_graph = hunt_graph

    def chat(self, body: ChatRequest) -> ChatResult:
        msg = (body.message or "").strip()
        if not msg:
            raise ValueError("message is required")

        run_id = body.run_id
        logger.info("chat: msg_len=%d, run_id=%s", len(msg), run_id)

        if self._hunt_graph is None:
            logger.info("No hunt graph (no API key) -> _chat_no_agent")
            return self._chat_no_agent(msg, run_id, ssh_config=body.ssh_config)

        created_run = False
        if run_id:
            run = self._runs.get(run_id)
            if not run:
                logger.warning("run_id %s not found", run_id)
                return ChatResult(reply="Run not found.", run_id=None, created_run=False)
            messages = list(run.messages)
            messages.append({"role": "user", "content": msg})
            self._runs.update(run_id, {"messages": messages})
            logger.debug("Using existing run %s, messages count=%d", run_id, len(messages))
        else:
            intent = _intent_parser.parse(msg)
            if intent:
                run_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                run = Run(
                    run_id=run_id,
                    target=intent.target,
                    scope=intent.scope or "",
                    objective=intent.objective or "comprehensive",
                    status="running",
                    created_at=now,
                    graph_state=GraphState(current_node="agent", completed_nodes=[]),
                    messages=[{"role": "user", "content": msg}],
                    ssh_config=body.ssh_config,
                )
                self._runs.create(run)
                messages = list(run.messages)
                created_run = True
                logger.info("Scan intent -> created run_id=%s, target=%s, deferred=True", run_id, intent.target)
            else:
                messages = [{"role": "user", "content": msg}]
                created_run = False
                logger.debug("No scan intent -> will invoke agent inline (no run)")

        if run_id:
            return ChatResult(
                reply="Hunt started. Watch the flow graph and reasoning panel for real-time progress.",
                run_id=run_id,
                created_run=created_run,
                deferred=True,
            )

        # No scan intent - simple chat reply
        return ChatResult(
            reply="Send a message like 'Scan https://example.com' to start a bug hunt.",
            run_id=None,
            created_run=False,
        )

    def _chat_no_agent(self, msg: str, run_id: str | None, ssh_config: dict | None = None) -> ChatResult:
        """No API key / agent: heuristic run creation or prompt to add key."""
        intent = _intent_parser.parse(msg)
        if intent:
            run_id_new = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            run = Run(
                run_id=run_id_new,
                target=intent.target,
                scope=intent.scope or "",
                objective=intent.objective or "comprehensive",
                status="queued",
                created_at=now,
                graph_state=GraphState(current_node="start", completed_nodes=[]),
                messages=[
                    {"role": "user", "content": msg},
                    {"role": "assistant", "content": f"Run created for {intent.target}. Add an API key in Settings to execute the multi-agent hunt."},
                ],
                ssh_config=ssh_config,
            )
            self._runs.create(run)
            return ChatResult(
                reply=f"Run created for {intent.target} (objective: {intent.objective}). Add an API key in Settings to execute the multi-agent hunt.",
                run_id=run_id_new,
                created_run=True,
            )
        return ChatResult(
            reply="Send a message like 'Scan https://example.com' to start a bug hunt. Add an API key in Settings for the agents to work.",
            run_id=run_id,
            created_run=False,
        )
