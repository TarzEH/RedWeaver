"""Serializers for the observability read API (the debug surface)."""
from rest_framework import serializers

from .models import (
    AgentStep,
    AgentTransition,
    EventLog,
    GraphSnapshot,
    Screenshot,
    ToolExecution,
)


class ToolExecutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ToolExecution
        fields = (
            "id", "run", "agent_step", "agent_name", "tool_name", "sequence",
            "argv", "command_str", "target", "scope", "options",
            "raw_stdout", "raw_stderr", "exit_code", "parsed_result",
            "truncated_for_llm", "started_at", "finished_at", "duration_ms",
            "status", "error",
        )


class AgentStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentStep
        fields = (
            "id", "run", "agent_name", "sequence", "step_type",
            "from_agent", "to_agent", "started_at", "finished_at", "duration_ms",
            "input_context", "reasoning_text", "output_summary",
            "structured_output", "confidence",
        )


class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = ("id", "run", "sequence", "event_type", "agent_name",
                  "timestamp", "payload")


class GraphSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = GraphSnapshot
        fields = ("id", "run", "sequence", "current_node", "active_nodes",
                  "completed_nodes", "plan", "nodes", "edges", "taken_at")


class AgentTransitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentTransition
        fields = ("id", "run", "from_agent", "to_agent", "sequence",
                  "edge_type", "reason", "created_at")


class ScreenshotSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    path = serializers.SerializerMethodField()

    class Meta:
        model = Screenshot
        fields = ("id", "run", "tool_execution", "agent_name", "tool_name",
                  "url", "final_url", "image_url", "path", "width", "height",
                  "bytes", "page_title", "http_status", "caption", "taken_at")

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    def get_path(self, obj):
        return obj.image.name if obj.image else None
