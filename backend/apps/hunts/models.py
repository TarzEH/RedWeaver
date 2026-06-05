"""Hunts: Session, Target (single-table), and Run (the execution + config).

Run collapses the legacy ``models.run.Run`` (execution/graph_state) and
``domain.hunt.Hunt`` (config) into one table — they were always 1:1 at start.
The legacy ``graph_state`` blob is replaced by normalized observability rows
(GraphSnapshot / AgentStep / Finding); ``graph_state`` here is a thin
read property that reconstructs the UI-facing shape from the latest snapshot.
"""
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedUUIDModel


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
class SessionStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ARCHIVED = "archived", "Archived"


class Session(TimeStampedUUIDModel):
    """A red-team engagement grouping hunts/targets (legacy domain.session)."""

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sessions",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    status = models.CharField(
        max_length=16, choices=SessionStatus.choices, default=SessionStatus.ACTIVE
    )
    tags = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.name


# ---------------------------------------------------------------------------
# Target (single-table; type-specific fields live in ``config`` JSONB)
# ---------------------------------------------------------------------------
class TargetType(models.TextChoices):
    WEBAPP = "webapp", "Web App"
    API = "api", "API"
    NETWORK = "network", "Network"
    HOST = "host", "Host"
    IDENTITY = "identity", "Identity"


_CLASSIFICATION = {
    TargetType.WEBAPP: "web",
    TargetType.API: "web",
    TargetType.NETWORK: "network",
    TargetType.HOST: "host",
    TargetType.IDENTITY: "web",
}


class Target(TimeStampedUUIDModel):
    """Single-table replacement for the discriminated Target union.

    ``config`` holds type-specific keys: url / base_url+spec_url / cidr_ranges+
    port_ranges / ip+ssh_config+os_hint / domain+email_patterns.
    """

    name = models.CharField(max_length=255)
    target_type = models.CharField(
        max_length=16, choices=TargetType.choices, db_index=True
    )
    session = models.ForeignKey(
        "hunts.Session",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="targets",
    )
    notes = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.target_type})"

    def address_string(self) -> str:
        """Primary address string for CrewFactory (mirrors target_to_string)."""
        c = self.config or {}
        if self.target_type == TargetType.WEBAPP:
            return c.get("url", "")
        if self.target_type == TargetType.API:
            return c.get("base_url", "")
        if self.target_type == TargetType.NETWORK:
            ranges = c.get("cidr_ranges") or []
            return ranges[0] if ranges else ""
        if self.target_type == TargetType.HOST:
            return c.get("ip", "")
        if self.target_type == TargetType.IDENTITY:
            return c.get("domain", "")
        return ""

    def classification(self) -> str:
        """CrewFactory classification: 'web' | 'network' | 'host'."""
        return _CLASSIFICATION.get(self.target_type, "web")


# ---------------------------------------------------------------------------
# Run (execution + config; parent of all observability rows)
# ---------------------------------------------------------------------------
class RunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class Run(TimeStampedUUIDModel):
    """A single hunt execution. Parent of agent steps, tool executions,
    events, graph snapshots, screenshots, findings and reports."""

    # Relationships
    session = models.ForeignKey(
        "hunts.Session",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="runs",
    )
    target_obj = models.ForeignKey(
        "hunts.Target",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )

    # Hunt config (legacy HuntConfig + Run fields)
    target = models.CharField(max_length=512, help_text="Resolved address string")
    scope = models.CharField(max_length=512, blank=True, default="")
    objective = models.CharField(max_length=128, default="comprehensive")
    agent_selection = models.JSONField(default=list, blank=True)
    # Pre-hunt ATT&CK plan: operator-selected MITRE ATT&CK technique ids (from the
    # ATT&CK Navigator). When set, the crew is scoped to the agents/tactics behind
    # these techniques and a focus directive is injected into every task.
    attack_focus = models.JSONField(default=list, blank=True)
    timeout_seconds = models.IntegerField(default=900)
    ssh_config = models.JSONField(null=True, blank=True)

    # Lifecycle
    status = models.CharField(
        max_length=16,
        choices=RunStatus.choices,
        default=RunStatus.QUEUED,
        db_index=True,
    )
    celery_task_id = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    # LLM cost accounting (captured from CrewAI token usage after kickoff)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    # Artifacts (report kept for the report API; messages = chat transcript)
    report_markdown = models.TextField(blank=True, default="")
    messages = models.JSONField(default=list, blank=True)

    # OffSec playbook (separate offensive-security agent, on-demand)
    offsec_markdown = models.TextField(blank=True, default="")
    offsec_status = models.CharField(max_length=16, default="none")  # none/queued/running/completed/failed

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session", "-created_at"]),
            models.Index(fields=["workspace", "-created_at"]),
            models.Index(fields=["status"]),
        ]


class NotificationChannel(TimeStampedUUIDModel):
    """Outbound notification target (generic webhook / Slack-compatible) fired
    on run completion or critical findings."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notification_channels",
    )
    workspace = models.ForeignKey(
        "workspaces.Workspace", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notification_channels",
    )
    name = models.CharField(max_length=128)
    kind = models.CharField(
        max_length=16,
        choices=[("webhook", "Webhook"), ("slack", "Slack")],
        default="webhook",
    )
    url = models.URLField(max_length=1024)
    events = models.JSONField(default=list, blank=True)  # [] = all; else subset
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.kind})"


class Schedule(TimeStampedUUIDModel):
    """A recurring scan: re-runs a target every interval (continuous monitoring)."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schedules",
    )
    session = models.ForeignKey(
        "hunts.Session", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schedules",
    )
    name = models.CharField(max_length=128)
    target = models.CharField(max_length=512)
    scope = models.CharField(max_length=512, blank=True, default="")
    objective = models.CharField(max_length=128, default="comprehensive")
    interval_minutes = models.IntegerField(default=1440)  # daily
    enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} -> {self.target} (every {self.interval_minutes}m)"

    def __str__(self) -> str:
        return f"Run<{self.id}> {self.target} [{self.status}]"

    @property
    def graph_state(self) -> dict:
        """Reconstruct the UI-facing graph state from the latest snapshot.

        Full step/finding reconstruction is done in the serializer (Phase E);
        this keeps the legacy ``/api/runs/{id}`` shape available cheaply.
        """
        snap = None
        try:
            snap = self.graph_snapshots.order_by("-sequence").first()
        except Exception:
            snap = None
        return {
            "current_node": getattr(snap, "current_node", None),
            "active_nodes": getattr(snap, "active_nodes", []) or [],
            "completed_nodes": getattr(snap, "completed_nodes", []) or [],
            "plan": getattr(snap, "plan", []) or [],
            "report_markdown": self.report_markdown or "",
        }
