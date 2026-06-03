"""Report routes (mounted at /api/)."""
from django.urls import path

from .views import run_report

urlpatterns = [
    path("runs/<uuid:run_id>/report", run_report, name="run-report"),
]
