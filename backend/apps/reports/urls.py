"""Report routes (mounted at /api/)."""
from django.urls import path

from .views import run_report, run_report_export

urlpatterns = [
    path("runs/<uuid:run_id>/report", run_report, name="run-report"),
    path("runs/<uuid:run_id>/report/export", run_report_export, name="run-report-export"),
]
