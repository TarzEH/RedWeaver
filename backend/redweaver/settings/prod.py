"""Production overlay."""
from .base import *  # noqa: F401,F403

DEBUG = False

# Security hardening (enable behind TLS termination).
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
