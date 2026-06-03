"""Channels middleware that authenticates the WS handshake via JWT.

Accepts the token from ?token=<jwt> (browser WebSocket can't set headers) or
an Authorization: Bearer header (non-browser clients).
"""
from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from .auth import get_user_from_token


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        token = None
        qs = parse_qs((scope.get("query_string") or b"").decode())
        if qs.get("token"):
            token = qs["token"][0]
        if not token:
            for name, value in scope.get("headers", []):
                if name == b"authorization":
                    raw = value.decode()
                    if raw.lower().startswith("bearer "):
                        token = raw[7:]
                    break
        scope["user"] = await get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
