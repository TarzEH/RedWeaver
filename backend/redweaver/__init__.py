"""RedWeaver Django project package.

Importing the Celery app here ensures the shared task decorator and the
``@shared_task`` autodiscovery work as soon as Django starts.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
