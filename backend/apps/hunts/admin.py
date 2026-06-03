"""Admin for hunts: Session, Target, Run.

Run is the debug hub — its inlines (agent steps, tool executions with raw
output, findings, snapshots, screenshots, events) are added in C2.
"""
from django.contrib import admin

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


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = (
        "id", "target", "status", "objective", "session",
        "finding_count", "created_by", "created_at",
    )
    list_filter = ("status", "objective")
    search_fields = ("id", "target", "scope", "session__name")
    date_hierarchy = "created_at"
    readonly_fields = ("id", "created_at", "updated_at", "started_at", "completed_at")
    raw_id_fields = ("session", "target_obj", "workspace", "created_by")

    @admin.display(description="Findings")
    def finding_count(self, obj) -> int:
        return obj.findings.count()
