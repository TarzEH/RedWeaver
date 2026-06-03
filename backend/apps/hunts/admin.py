"""Admin for hunts: Session, Target, and the Run debug hub.

Opening one Run shows the entire behind-the-scenes record inline: agent
steps, tool executions (with raw output via their change page), findings,
graph snapshots, and screenshots. The high-volume event log + transitions +
huntflow are linked (not inlined) to keep the page fast.
"""
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.findings.models import Finding
from apps.observability.models import (
    AgentStep,
    GraphSnapshot,
    Screenshot,
    ToolExecution,
)

from .models import Run, Session, Target


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("workspace", "created_by")


@admin.register(Target)
class TargetAdmin(admin.ModelAdmin):
    list_display = ("name", "target_type", "session", "created_at")
    list_filter = ("target_type",)
    search_fields = ("name", "notes")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("session",)


# --------------------------------------------------------------------------- #
# Read-only inlines for the Run hub
# --------------------------------------------------------------------------- #
class _ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class AgentStepInline(_ReadOnlyInline):
    model = AgentStep
    fields = ("sequence", "agent_name", "step_type", "from_agent",
              "to_agent", "confidence", "duration_ms")
    readonly_fields = fields
    ordering = ("sequence",)


class ToolExecutionInline(_ReadOnlyInline):
    model = ToolExecution
    fields = ("sequence", "tool_name", "agent_name", "status",
              "exit_code", "duration_ms")
    readonly_fields = fields
    ordering = ("sequence",)


class FindingInline(_ReadOnlyInline):
    model = Finding
    fields = ("severity", "title", "status", "confidence",
              "agent_source", "tool_used")
    readonly_fields = fields


class GraphSnapshotInline(_ReadOnlyInline):
    model = GraphSnapshot
    fields = ("sequence", "current_node", "taken_at")
    readonly_fields = fields
    ordering = ("sequence",)


class ScreenshotInline(_ReadOnlyInline):
    model = Screenshot
    fields = ("thumb", "url", "agent_name", "taken_at")
    readonly_fields = ("thumb", "url", "agent_name", "taken_at")

    @admin.display(description="preview")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:48px;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "target", "status", "objective", "session",
        "finding_count", "created_by", "created_at",
    )
    list_filter = ("status", "objective")
    search_fields = ("id", "target", "scope", "session__name")
    date_hierarchy = "created_at"
    raw_id_fields = ("session", "target_obj", "workspace", "created_by")
    readonly_fields = (
        "id", "created_at", "updated_at", "started_at", "completed_at",
        "behind_the_scenes",
    )
    inlines = [
        AgentStepInline,
        ToolExecutionInline,
        FindingInline,
        GraphSnapshotInline,
        ScreenshotInline,
    ]
    fieldsets = (
        ("Run", {"fields": ("id", "status", "target", "scope", "objective",
                            "agent_selection", "timeout_seconds", "ssh_config")}),
        ("Links", {"fields": ("session", "target_obj", "workspace", "created_by")}),
        ("Lifecycle", {"fields": ("started_at", "completed_at", "error_message",
                                  "created_at", "updated_at")}),
        ("Behind the scenes", {"fields": ("behind_the_scenes", "report_markdown")}),
    )

    @admin.display(description="Findings")
    def finding_count(self, obj) -> int:
        return obj.findings.count()

    @admin.display(description="Full event stream / transitions / huntflow")
    def behind_the_scenes(self, obj):
        """Links to the high-volume observability tables filtered to this run."""
        def link(model: str, label: str, count: int) -> str:
            url = reverse(f"admin:observability_{model}_changelist")
            return format_html(
                '<a href="{}?run__id__exact={}">{} ({})</a>', url, obj.id, label, count
            )

        parts = [
            link("eventlog", "Event log", obj.events.count()),
            link("agenttransition", "Transitions", obj.transitions.count()),
            link("huntflownode", "Huntflow nodes", obj.huntflow_nodes.count()),
            link("toolexecution", "Tool executions", obj.tool_executions.count()),
        ]
        return format_html(" &nbsp;|&nbsp; ".join("{}" for _ in parts), *parts)
