"""Admin for reports."""
from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "template", "run", "session", "generated_by", "created_at")
    list_filter = ("template",)
    search_fields = ("title", "executive_summary")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("run", "session", "generated_by")
