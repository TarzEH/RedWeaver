"""Admin for observability — the behind-the-scenes debug surface.

All rows are machine-written: read-only (no add/change), but viewable and
deletable. Raw tool output, JSON payloads and screenshots are rendered inline.
"""
from django.contrib import admin
from django.utils.html import format_html

from apps.common.admin import ReadOnlyAdminMixin, pre_block, pretty_json

from .models import (
    AgentStep,
    AgentTransition,
    EventLog,
    GraphSnapshot,
    HuntflowNode,
    Screenshot,
    ToolExecution,
)


@admin.register(ToolExecution)
class ToolExecutionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "tool_name", "agent_name", "status", "exit_code",
        "duration_ms", "sequence", "run", "started_at",
    )
    list_filter = ("status", "tool_name", "agent_name")
    search_fields = ("tool_name", "command_str", "run__target")
    raw_id_fields = ("run", "agent_step")
    readonly_fields = (
        "id", "run", "agent_step", "agent_name", "tool_name", "sequence",
        "command_str", "argv_json", "target", "scope", "options_json",
        "stdout_pre", "stderr_pre", "exit_code", "parsed_result_json",
        "truncated_for_llm", "status", "error",
        "started_at", "finished_at", "duration_ms", "created_at",
    )

    @admin.display(description="argv")
    def argv_json(self, obj):
        return pretty_json(obj.argv)

    @admin.display(description="options")
    def options_json(self, obj):
        return pretty_json(obj.options)

    @admin.display(description="parsed_result")
    def parsed_result_json(self, obj):
        return pretty_json(obj.parsed_result)

    @admin.display(description="raw stdout")
    def stdout_pre(self, obj):
        return pre_block(obj.raw_stdout)

    @admin.display(description="raw stderr")
    def stderr_pre(self, obj):
        return pre_block(obj.raw_stderr)


@admin.register(AgentStep)
class AgentStepAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "sequence", "agent_name", "step_type", "from_agent", "to_agent",
        "confidence", "duration_ms", "run",
    )
    list_filter = ("step_type", "agent_name")
    search_fields = ("agent_name", "reasoning_text", "output_summary", "run__target")
    raw_id_fields = ("run",)
    readonly_fields = (
        "id", "run", "agent_name", "sequence", "step_type",
        "from_agent", "to_agent", "started_at", "finished_at", "duration_ms",
        "input_context_json", "reasoning_text", "output_summary",
        "structured_output_json", "confidence", "created_at",
    )

    @admin.display(description="input_context")
    def input_context_json(self, obj):
        return pretty_json(obj.input_context)

    @admin.display(description="structured_output")
    def structured_output_json(self, obj):
        return pretty_json(obj.structured_output)


@admin.register(AgentTransition)
class AgentTransitionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("from_agent", "to_agent", "edge_type", "sequence", "run")
    list_filter = ("edge_type",)
    search_fields = ("from_agent", "to_agent", "run__target")
    raw_id_fields = ("run",)


@admin.register(EventLog)
class EventLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("sequence", "event_type", "agent_name", "timestamp", "run")
    list_filter = ("event_type",)
    search_fields = ("event_type", "agent_name", "run__target")
    raw_id_fields = ("run",)
    readonly_fields = (
        "id", "run", "sequence", "event_type", "agent_name",
        "timestamp", "payload_json", "created_at",
    )

    @admin.display(description="payload")
    def payload_json(self, obj):
        return pretty_json(obj.payload)


@admin.register(GraphSnapshot)
class GraphSnapshotAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("sequence", "current_node", "taken_at", "run")
    search_fields = ("current_node", "run__target")
    raw_id_fields = ("run",)
    readonly_fields = (
        "id", "run", "sequence", "current_node",
        "active_nodes_json", "completed_nodes_json", "plan_json",
        "nodes_json", "edges_json", "taken_at", "created_at",
    )

    @admin.display(description="active_nodes")
    def active_nodes_json(self, obj):
        return pretty_json(obj.active_nodes)

    @admin.display(description="completed_nodes")
    def completed_nodes_json(self, obj):
        return pretty_json(obj.completed_nodes)

    @admin.display(description="plan")
    def plan_json(self, obj):
        return pretty_json(obj.plan)

    @admin.display(description="nodes")
    def nodes_json(self, obj):
        return pretty_json(obj.nodes)

    @admin.display(description="edges")
    def edges_json(self, obj):
        return pretty_json(obj.edges)


@admin.register(HuntflowNode)
class HuntflowNodeAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("node_type", "agent_name", "sequence", "parent", "run")
    list_filter = ("node_type", "agent_name")
    search_fields = ("content", "run__target")
    raw_id_fields = ("run", "parent")


@admin.register(Screenshot)
class ScreenshotAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("thumb", "url", "agent_name", "tool_name", "taken_at", "run")
    list_filter = ("agent_name", "tool_name")
    search_fields = ("url", "page_title", "run__target")
    raw_id_fields = ("run", "tool_execution")
    readonly_fields = (
        "id", "run", "tool_execution", "agent_name", "tool_name",
        "url", "final_url", "preview", "width", "height", "bytes",
        "page_title", "http_status", "caption", "taken_at", "created_at",
    )

    @admin.display(description="")
    def thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="preview")
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width:720px;border-radius:6px;" />',
                obj.image.url,
            )
        return "—"
