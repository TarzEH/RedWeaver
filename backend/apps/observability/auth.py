"""Resolve a user from a JWT for the WebSocket handshake."""
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def get_user_from_token(token: str):
    if not token:
        return AnonymousUser()
    try:
        from rest_framework_simplejwt.tokens import AccessToken

        access = AccessToken(token)
        user_id = access["user_id"]
    except Exception:
        return AnonymousUser()
    User = get_user_model()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()
