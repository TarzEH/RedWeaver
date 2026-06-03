"""Settings package — selects an environment overlay via DJANGO_ENV.

DJANGO_SETTINGS_MODULE stays ``redweaver.settings`` everywhere; the concrete
overlay (dev/prod/test) is chosen by the DJANGO_ENV environment variable so we
never have to juggle multiple settings module paths across compose services.
"""
import os

_env = os.environ.get("DJANGO_ENV", "dev").lower()

from .base import *  # noqa: F401,F403

if _env == "prod":
    from .prod import *  # noqa: F401,F403
elif _env == "test":
    from .test import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
