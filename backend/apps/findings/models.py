"""Findings: first-class security findings with dedup, triage, and reliability."""
import hashlib

from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Severity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MEDIUM = "medium", "Medium"
    LOW = "low", "Low"
    INFO = "info", "Info"


class FindingStatus(models.TextChoices):
    NEW = "new", "New"
    CONFIRMED = "confirmed", "Confirmed"
    FALSE_POSITIVE = "false_positive", "False positive"
    ACCEPTED_RISK = "accepted_risk", "Accepted risk"
    REMEDIATED = "remediated", "Remediated"


class Exploitability(models.TextChoices):
    PROVEN = "proven", "Proven"
    LIKELY = "likely", "Likely"
    POSSIBLE = "possible", "Possible"
    UNLIKELY = "unlikely", "Unlikely"
    UNKNOWN = "unknown", "Unknown"


class Finding(TimeStampedUUIDModel):
    """Replaces legacy domain.finding.Finding + crew schemas.FindingItem.

    Adds reliability/confidence as first-class, queryable fields and a link
    back to the raw ToolExecution that produced the finding.
    """

    # Relationships (run is canonical; session/target denormalized for filters)
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="findings"
    )
    session = models.ForeignKey(
        "hunts.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="findings",
    )
    target = models.ForeignKey(
        "hunts.Target",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="findings",
    )
    source_tool_execution = models.ForeignKey(
        "observability.ToolExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="findings",
    )

    # Core finding fields
    title = models.CharField(max_length=512)
    severity = models.CharField(
        max_length=16, choices=Severity.choices, default=Severity.INFO, db_index=True
    )
    description = models.TextField(blank=True, default="")
    affected_url = models.CharField(max_length=2048, blank=True, default="")
    evidence = models.TextField(blank=True, default="")
    remediation = models.TextField(blank=True, default="")
    agent_source = models.CharField(max_length=64, blank=True, default="")
    tool_used = models.CharField(max_length=128, blank=True, default="")
    cvss_score = models.FloatField(null=True, blank=True)
    cve_ids = models.JSONField(default=list, blank=True)

    # Triage
    status = models.CharField(
        max_length=20,
        choices=FindingStatus.choices,
        default=FindingStatus.NEW,
        db_index=True,
    )

    # Reliability / confidence (NEW — first-class debug signal)
    confidence = models.FloatField(null=True, blank=True, help_text="0.0–1.0")
    exploitability = models.CharField(
        max_length=16,
        choices=Exploitability.choices,
        default=Exploitability.UNKNOWN,
    )
    cisa_kev = models.BooleanField(default=False)
    epss_score = models.FloatField(null=True, blank=True, help_text="EPSS exploit probability 0..1")
    verified_by_agent = models.CharField(max_length=64, blank=True, default="")

    # Deduplication
    dedup_key = models.CharField(max_length=32, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["run", "severity"]),
            models.Index(fields=["session", "status"]),
            models.Index(fields=["dedup_key"]),
        ]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.title}"

    def compute_dedup_key(self) -> str:
        raw = (
            f"{(self.title or '').lower().strip()}|"
            f"{(self.affected_url or '').lower().strip()}|"
            f"{self.severity}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def save(self, *args, **kwargs):
        if not self.dedup_key:
            self.dedup_key = self.compute_dedup_key()
        super().save(*args, **kwargs)
