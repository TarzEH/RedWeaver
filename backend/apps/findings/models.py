"""Findings: first-class security findings with dedup, triage, and reliability."""
import hashlib

from django.conf import settings
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
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_findings",
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
    # Cross-run correlation key (title+url, severity-independent) so the same
    # issue is matched across runs/scans for trend/regression tracking.
    normalized_key = models.CharField(max_length=32, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["run", "severity"]),
            models.Index(fields=["session", "status"]),
            models.Index(fields=["dedup_key"]),
            models.Index(fields=["normalized_key"]),
        ]

    def __str__(self) -> str:
        return f"[{self.severity}] {self.title}"

    @staticmethod
    def _norm_title(title: str) -> str:
        import re
        t = (title or "").lower().strip()
        t = re.sub(r"\b(?:cve-\d{4}-\d+|port\s*\d+|\d+)\b", "", t)  # drop volatile ids/ports
        return re.sub(r"\s+", " ", t).strip()

    def compute_dedup_key(self) -> str:
        raw = (
            f"{(self.title or '').lower().strip()}|"
            f"{(self.affected_url or '').lower().strip()}|"
            f"{self.severity}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def compute_normalized_key(self) -> str:
        raw = f"{self._norm_title(self.title)}|{(self.affected_url or '').lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def save(self, *args, **kwargs):
        if not self.dedup_key:
            self.dedup_key = self.compute_dedup_key()
        if not self.normalized_key:
            self.normalized_key = self.compute_normalized_key()
        super().save(*args, **kwargs)


class AttackChain(TimeStampedUUIDModel):
    """A correlated multi-step attack path produced by the exploit_analyst —
    previously computed and thrown away; now persisted for the report/UI."""

    run = models.ForeignKey("hunts.Run", on_delete=models.CASCADE, related_name="attack_chains")
    name = models.CharField(max_length=256)
    description = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.MEDIUM)
    steps = models.JSONField(default=list, blank=True)
    findings = models.ManyToManyField(Finding, blank=True, related_name="attack_chains")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class FindingComment(TimeStampedUUIDModel):
    """Analyst collaboration on a finding."""

    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="finding_comments"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]


class FindingActivity(TimeStampedUUIDModel):
    """Auditable timeline of triage actions (status/assignee/retest/comment)."""

    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="finding_activity"
    )
    action = models.CharField(max_length=32)  # status_change / assigned / comment / retest
    detail = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
