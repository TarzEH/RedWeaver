"""WebSocket URL routing for run event streams."""
from django.urls import re_path

from .consumers import RunConsumer

websocket_urlpatterns = [
    re_path(r"^ws/runs/(?P<run_id>[0-9a-fA-F-]+)/stream/?$", RunConsumer.as_asgi()),
]
