"""Base Django settings for RedWeaver.

Read from the environment with django-environ. Docker compose supplies every
variable; sensible dev defaults keep `manage.py` usable outside containers.
"""
from pathlib import Path

import environ

# backend/redweaver/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "web"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:5173", "http://localhost:8001"]),
    CORS_ALLOW_ALL_ORIGINS=(bool, True),
)

# Load a local .env file if present (no-op in Docker where env is injected).
_env_file = BASE_DIR.parent / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ----------------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# ----------------------------------------------------------------------------
# Applications
# ----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "daphne",  # must precede staticfiles for runserver ASGI; harmless otherwise
    "channels",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.workspaces",
    "apps.hunts",
    "apps.findings",
    "apps.observability",
    "apps.reports",
    "apps.agents",
    "apps.knowledge",
]

# daphne injects its own ASGI handling; keep it first so runserver uses ASGI.
INSTALLED_APPS = ["daphne"] + DJANGO_APPS + [
    a for a in THIRD_PARTY_APPS if a != "daphne"
] + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "redweaver.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "redweaver.wsgi.application"
ASGI_APPLICATION = "redweaver.asgi.application"

# ----------------------------------------------------------------------------
# Database (PostgreSQL — system of record)
# ----------------------------------------------------------------------------
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://redweaver:redweaver@localhost:5433/redweaver",
    ),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ----------------------------------------------------------------------------
# Channels (WebSocket real-time over Redis)
# ----------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("CHANNEL_LAYERS_URL", default="redis://localhost:6380/1")],
        },
    },
}

# ----------------------------------------------------------------------------
# Celery (out-of-process crew.kickoff)
# ----------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6380/2")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=1800)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=1700)
CELERY_WORKER_CONCURRENCY = env.int("CREW_EXECUTOR_WORKERS", default=4)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Live pub/sub Redis (separate DB from Channels/Celery).
REDIS_URL = env("REDIS_URL", default="redis://localhost:6380/0")

# ----------------------------------------------------------------------------
# Django REST Framework + JWT
# ----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # No global pagination: legacy frontend list endpoints return plain arrays.
    # Observability/debug viewsets opt in to pagination explicitly.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    # Rate limiting (brute-force / abuse protection). "auth" is a tight scope
    # applied to login/register; "llm" guards the provider-proxy endpoints.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "user": env("THROTTLE_USER", default="2000/hour"),
        "anon": env("THROTTLE_ANON", default="120/hour"),
        "auth": env("THROTTLE_AUTH", default="20/min"),
        "llm": env("THROTTLE_LLM", default="60/min"),
    },
}

from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_MINUTES", default=60)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_DAYS", default=7)
    ),
    # Keep token compatibility with the legacy JWT_SECRET if provided;
    # fall back to SECRET_KEY when JWT_SECRET is unset OR an empty string.
    "SIGNING_KEY": env("JWT_SECRET", default="") or SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RedWeaver API",
    "DESCRIPTION": "Multi-agent bug-hunting automation",
    "VERSION": "0.4.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ----------------------------------------------------------------------------
# CORS
# ----------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ----------------------------------------------------------------------------
# Static & media
# ----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", default="/app/media")

# Screenshots live under MEDIA_ROOT; this absolute dir is what Playwright writes.
SCREENSHOTS_DIR = env(
    "SCREENSHOTS_DIR", default=str(Path(MEDIA_ROOT) / "screenshots")
)
SCREENSHOT_TIMEOUT_SEC = env.int("SCREENSHOT_TIMEOUT_SEC", default=30)
SCREENSHOT_MAX_PER_RUN = env.int("SCREENSHOT_MAX_PER_RUN", default=50)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# ----------------------------------------------------------------------------
# Passwords / i18n / misc
# ----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------------
# Engine config passthrough (consumed by redweaver_engine + agents)
# ----------------------------------------------------------------------------
KNOWLEDGE_SERVICE_URL = env(
    "KNOWLEDGE_SERVICE_URL", default="http://localhost:8100"
)

# Multi-agent orchestration engine: "crewai" (default) or "deepagents".
# See docs/refactor-deepagents-ragas.md — deepagents is migrated incrementally
# behind this flag; CrewAI remains the default until parity is proven.
HUNT_ENGINE = env("HUNT_ENGINE", default="crewai").lower()

# ----------------------------------------------------------------------------
# KB embedding provider (pgvector RAG) — pick where the vectors come from.
#   openai      -> OpenAI text-embedding-3-small (1536 dims, needs an API key)
#   huggingface -> local sentence-transformers via LangChain (fully offline,
#                  no key); default model all-MiniLM-L6-v2 = 384 dims
# KB_EMBED_DIM must match the model's output dimension; migration 0003 aligns
# the pgvector column to it. Switching provider requires a re-ingest (ingest_kb).
# ----------------------------------------------------------------------------
KB_EMBED_PROVIDER = env("KB_EMBED_PROVIDER", default="openai").lower()
KB_EMBED_MODEL = env("KB_EMBED_MODEL", default="")  # blank -> provider default
# Parse defensively: Compose passes an empty string when the var is unset, which
# env.int() would choke on. Blank -> provider-appropriate default.
_kb_embed_dim_raw = env("KB_EMBED_DIM", default="")
KB_EMBED_DIM = (
    int(_kb_embed_dim_raw)
    if str(_kb_embed_dim_raw).strip()
    else (384 if KB_EMBED_PROVIDER == "huggingface" else 1536)
)
KB_EMBED_DEVICE = env("KB_EMBED_DEVICE", default="cpu") or "cpu"  # cpu | cuda (HF)
# Fernet key for ApiKeyVault secret encryption (falls back to derived from SECRET_KEY).
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

# ---------------------------------------------------------------------------
# Error monitoring (Sentry) — only initialized when SENTRY_DSN is configured.
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
            send_default_pii=False,
            environment=env("DJANGO_ENV", default="dev"),
        )
    except Exception:  # never let monitoring setup break boot
        pass
