"""Celery application for out-of-process hunt execution (crew.kickoff)."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "redweaver.settings")

app = Celery("redweaver")

# All Celery settings live in Django settings under the CELERY_ namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py modules in every installed app.
app.autodiscover_tasks()

# Periodic scan scheduler — fires every minute and runs any due Schedule rows.
app.conf.beat_schedule = {
    "run-due-schedules": {
        "task": "apps.hunts.tasks.run_due_schedules",
        "schedule": 60.0,
    },
    # Watchdog: fail runs orphaned by a worker restart/crash (stuck in 'running'
    # past their timeout). Runs every 2 minutes.
    "reap-stuck-runs": {
        "task": "apps.hunts.tasks.reap_stuck_runs",
        "schedule": 120.0,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # pragma: no cover - smoke test helper
    print(f"Request: {self.request!r}")
