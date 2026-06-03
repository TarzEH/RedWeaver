"""Admin for findings."""
from django.contrib import admin

from .models import Finding


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = (
        "title", "severity", "status", "confidence", "exploitability",
        "cisa_kev", "agent_source", "tool_used", "run", "created_at",
    )
    list_filter = ("severity", "status", "exploitability", "cisa_kev", "agent_source")
    search_fields = ("title", "affected_url", "description", "dedup_key")
    readonly_fields = ("id", "created_at", "updated_at", "dedup_key")
    raw_id_fields = ("run", "session", "target", "source_tool_execution")
    list_select_related = ("run",)
