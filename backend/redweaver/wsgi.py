"""WSGI entrypoint (used only if a sync-only deployment is ever needed)."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redweaver.settings")

application = get_wsgi_application()
