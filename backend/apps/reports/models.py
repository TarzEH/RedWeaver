"""Reports: persisted report artifacts generated from a run's findings."""
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedUUIDModel


class ReportTemplate(models.TextChoices):
    PROFESSIONAL = "professional", "Professional"
    EXECUTIVE = "executive", "Executive"
    CUSTOM = "custom", "Custom"


class Report(TimeStampedUUIDModel):
    """Replaces legacy domain.report.Report.

    ``hunt_ids``/``finding_ids`` lists relax into a Run FK (+ reverse access to
    that run's findings); ``ReportData`` etc. stay as on-demand Pydantic DTOs
    in redweaver_engine.reports.generator.
    """

    run = models.ForeignKey(
        "hunts.Run",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    session = models.ForeignKey(
        "hunts.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )
    title = models.CharField(max_length=512, blank=True, default="")
    template = models.CharField(
        max_length=16,
        choices=ReportTemplate.choices,
        default=ReportTemplate.PROFESSIONAL,
    )
    report_markdown = models.TextField(blank=True, default="")
    executive_summary = models.TextField(blank=True, default="")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
    )

    def __str__(self) -> str:
        return self.title or f"Report run={self.run_id}"
