"""Production overlay."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

# Security hardening (enable behind TLS termination).
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HTTPS enforcement + HSTS.
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Never allow all CORS origins in production — require an explicit allow-list.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
]

# Fail fast on insecure defaults: a prod boot must not run on the dev secret,
# and the vault encryption key must not be silently derived from it.
_INSECURE_SECRETS = {"", "dev-insecure-change-me", "change-me"}
if SECRET_KEY in _INSECURE_SECRETS:  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a strong, unique value in production."
    )
if not os.environ.get("FIELD_ENCRYPTION_KEY"):
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY must be set in production "
        "(do not derive the ApiKeyVault key from SECRET_KEY)."
    )
