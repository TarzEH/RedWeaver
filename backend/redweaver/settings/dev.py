"""Development overlay."""
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

# Serve media through Django in dev (see redweaver/urls.py).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
