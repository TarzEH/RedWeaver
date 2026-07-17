"""RunConsumer — per-run WebSocket: DB replay on connect, then live events.

Replaces the legacy SSE endpoint + in-memory EventBus buffer. Reconnect-safe:
the client may pass ?last_seq=N and only the gap is replayed from EventLog.
"""
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import EventLog


class RunConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.run_id = self.scope["url_route"]["kwargs"]["run_id"]
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            await self.close(code=4401)
            return
        if not await self._can_access_run(user):
            await self.close(code=4403)  # authenticated but not authorized for this run
            return
        self.group = f"run_{self.run_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        qs = parse_qs((self.scope.get("query_string") or b"").decode())
        try:
            after = int(qs.get("last_seq", ["0"])[0])
        except (TypeError, ValueError):
            after = 0
        await self._replay(after)

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        # Control frames only (resume / ping).
        try:
            msg = json.loads(text_data or "{}")
        except (TypeError, ValueError):
            return
        if msg.get("action") == "resume":
            await self._replay(int(msg.get("last_seq") or 0))

    async def run_event(self, message):
        """Handler for channel_layer.group_send(type='run.event')."""
        await self.send(text_data=json.dumps(message["envelope"]))

    @database_sync_to_async
    def _can_access_run(self, user) -> bool:
        from apps.common.access import run_scope_q
        from apps.hunts.models import Run

        if getattr(user, "is_superuser", False):
            return Run.objects.filter(id=self.run_id).exists()
        return Run.objects.filter(run_scope_q(user)).filter(id=self.run_id).exists()

    @database_sync_to_async
    def _fetch(self, after):
        return list(
            EventLog.objects.filter(run_id=self.run_id, sequence__gt=after)
            .order_by("sequence")
            .values("sequence", "event_type", "agent_name", "payload")
        )

    async def _replay(self, after):
        last = after
        for ev in await self._fetch(after):
            last = ev["sequence"]
            await self.send(text_data=json.dumps({
                "type": ev["event_type"],
                "run_id": str(self.run_id),
                "seq": ev["sequence"],
                "agent": ev["agent_name"],
                "replay": True,
                "data": ev["payload"],
            }))
        await self.send(text_data=json.dumps({
            "type": "replay_complete",
            "run_id": str(self.run_id),
            "data": {"last_seq": last},
        }))
