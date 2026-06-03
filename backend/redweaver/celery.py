"""Celery application for out-of-process hunt execution (crew.kickoff)."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redweaver.settings")

app = Celery("redweaver")

# All Celery settings live in Django settings under the CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py modules in every installed app.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - smoke test helper
    print(f"Request: {self.request!r}")
