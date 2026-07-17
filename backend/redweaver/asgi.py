"""ASGI entrypoint — HTTP (Django/DRF) + WebSocket (Channels).

The WebSocket stack (apps.observability.middleware / routing) is wired in
Phase F. We import it defensively so the ASGI app still boots for the
HTTP-only phases before the consumers exist.
"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redweaver.settings")
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

_routers = {"http": django_asgi_app}

try:  # WebSocket stack lands in Phase F (RunConsumer + JWT middleware).
    from apps.observability.middleware import JWTAuthMiddlewareStack
    from apps.observability.routing import websocket_urlpatterns

    _routers["websocket"] = JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    )
except Exception:  # pragma: no cover - until Phase F is implemented
    pass

application = ProtocolTypeRouter(_routers)
