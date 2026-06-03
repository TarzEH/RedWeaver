"""Observability: the behind-the-scenes record of every run.

These tables are the heart of the upgrade — they persist what the legacy
system only streamed and threw away: every event, raw tool output, agent
reasoning/transition, topology snapshot, reasoning-tree node, and screenshot.
All rows are machine-written (read-only in Admin) and carry a per-run
``sequence`` so a run can be replayed deterministically.
"""
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedUUIDModel


# ---------------------------------------------------------------------------
# Agent steps (reasoning timeline) + transitions
# ---------------------------------------------------------------------------
class StepType(models.TextChoices):
    AGENT_START = "agent_start", "Agent start"
    THINKING = "thinking", "Thinking"
    TOOL_CALL = "tool_call", "Tool call"
    TOOL_RESULT = "tool_result", "Tool result"
    AGENT_COMPLETE = "agent_complete", "Agent complete"
    HANDOFF = "handoff", "Handoff"
    FINDING = "finding", "Finding"
    ERROR = "error", "Error"


class AgentStep(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="agent_steps"
    )
    agent_name = models.CharField(max_length=64, db_index=True, blank=True, default="")
    sequence = models.PositiveIntegerField(default=0, db_index=True)
    step_type = models.CharField(max_length=24, choices=StepType.choices)
    from_agent = models.CharField(max_length=64, blank=True, default="")
    to_agent = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    input_context = models.JSONField(null=True, blank=True)
    reasoning_text = models.TextField(blank=True, default="")
    output_summary = models.TextField(blank=True, default="")
    structured_output = models.JSONField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["run", "sequence"]
        indexes = [
            models.Index(fields=["run", "sequence"]),
            models.Index(fields=["run", "agent_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.agent_name}:{self.step_type}#{self.sequence}"


class AgentTransition(TimeStampedUUIDModel):
    """Explicit edge list for the topology view (orchestrator/context/handoff)."""

    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="transitions"
    )
    from_agent = models.CharField(max_length=64, blank=True, default="")
    to_agent = models.CharField(max_length=64, blank=True, default="")
    sequence = models.PositiveIntegerField(default=0, db_index=True)
    edge_type = models.CharField(max_length=24, default="context")
    reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["run", "sequence"]

    def __str__(self) -> str:
        return f"{self.from_agent} -> {self.to_agent}"


# ---------------------------------------------------------------------------
# Tool executions (raw command + stdout/stderr — the key new audit table)
# ---------------------------------------------------------------------------
class ToolStatus(models.TextChoices):
    RUNNING = "running", "Running"
    SUCCESS = "success", "Success"
    ERROR = "error", "Error"
    TIMEOUT = "timeout", "Timeout"
    UNAVAILABLE = "unavailable", "Unavailable"


class ToolExecution(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="tool_executions"
    )
    agent_step = models.ForeignKey(
        "observability.AgentStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tool_executions",
    )
    agent_name = models.CharField(max_length=64, blank=True, default="")
    tool_name = models.CharField(max_length=128, db_index=True)
    sequence = models.PositiveIntegerField(default=0, db_index=True)
    argv = models.JSONField(default=list, blank=True)
    command_str = models.TextField(blank=True, default="")
    target = models.CharField(max_length=512, blank=True, default="")
    scope = models.CharField(max_length=512, blank=True, default="")
    options = models.JSONField(default=dict, blank=True)
    raw_stdout = models.TextField(blank=True, default="")
    raw_stderr = models.TextField(blank=True, default="")
    exit_code = models.IntegerField(null=True, blank=True)
    parsed_result = models.JSONField(null=True, blank=True)
    truncated_for_llm = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16, choices=ToolStatus.choices, default=ToolStatus.RUNNING
    )
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["run", "sequence"]
        indexes = [
            models.Index(fields=["run", "sequence"]),
            models.Index(fields=["tool_name"]),
            models.Index(fields=["run", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.tool_name}[{self.status}] run={self.run_id}"


# ---------------------------------------------------------------------------
# Event log (verbatim stream — source of truth for replay)
# ---------------------------------------------------------------------------
class EventLog(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="events"
    )
    sequence = models.PositiveIntegerField(db_index=True)
    event_type = models.CharField(max_length=48, db_index=True)
    agent_name = models.CharField(max_length=64, blank=True, default="")
    timestamp = models.DateTimeField(default=timezone.now)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["run", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "sequence"], name="uniq_event_run_sequence"
            )
        ]
        indexes = [models.Index(fields=["run", "sequence"])]

    def __str__(self) -> str:
        return f"{self.event_type}#{self.sequence} run={self.run_id}"


# ---------------------------------------------------------------------------
# Graph snapshots (topology evolution)
# ---------------------------------------------------------------------------
class GraphSnapshot(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="graph_snapshots"
    )
    sequence = models.PositiveIntegerField(default=0, db_index=True)
    current_node = models.CharField(max_length=64, null=True, blank=True)
    active_nodes = models.JSONField(default=list, blank=True)
    completed_nodes = models.JSONField(default=list, blank=True)
    plan = models.JSONField(default=list, blank=True)
    nodes = models.JSONField(default=list, blank=True)
    edges = models.JSONField(default=list, blank=True)
    taken_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run", "sequence"]
        indexes = [models.Index(fields=["run", "sequence"])]

    def __str__(self) -> str:
        return f"snapshot#{self.sequence} run={self.run_id}"


# ---------------------------------------------------------------------------
# Huntflow reasoning tree (parent/child)
# ---------------------------------------------------------------------------
class HuntflowNodeType(models.TextChoices):
    HUNT_ROOT = "hunt_root", "Hunt root"
    AGENT_TASK = "agent_task", "Agent task"
    REASONING = "reasoning", "Reasoning"
    TOOL_CALL = "tool_call", "Tool call"
    TOOL_RESULT = "tool_result", "Tool result"
    FINDING = "finding", "Finding"
    PLAN_UPDATE = "plan_update", "Plan update"
    HANDOFF = "handoff", "Handoff"
    ERROR = "error", "Error"


class HuntflowNode(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="huntflow_nodes"
    )
    node_id = models.UUIDField(db_index=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    node_type = models.CharField(max_length=24, choices=HuntflowNodeType.choices)
    agent_name = models.CharField(max_length=64, blank=True, default="")
    content = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    sequence = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ordering = ["run", "sequence"]

    def __str__(self) -> str:
        return f"{self.node_type} run={self.run_id}"


# ---------------------------------------------------------------------------
# Screenshots (files on volume, path + metadata in DB)
# ---------------------------------------------------------------------------
class Screenshot(TimeStampedUUIDModel):
    run = models.ForeignKey(
        "hunts.Run", on_delete=models.CASCADE, related_name="screenshots"
    )
    tool_execution = models.ForeignKey(
        "observability.ToolExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="screenshots",
    )
    agent_name = models.CharField(max_length=64, blank=True, default="")
    tool_name = models.CharField(max_length=128, blank=True, default="")
    url = models.URLField(max_length=2048, blank=True, default="")
    final_url = models.URLField(max_length=2048, blank=True, default="")
    image = models.ImageField(upload_to="screenshots/%Y/%m/%d/", max_length=512)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    bytes = models.IntegerField(null=True, blank=True)
    page_title = models.CharField(max_length=512, blank=True, default="")
    http_status = models.IntegerField(null=True, blank=True)
    caption = models.CharField(max_length=512, blank=True, default="")
    taken_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["run", "-taken_at"]
        indexes = [models.Index(fields=["run"])]

    def __str__(self) -> str:
        return f"screenshot {self.url} run={self.run_id}"
