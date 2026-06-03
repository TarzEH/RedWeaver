"""Admin for workspaces."""
from django.contrib import admin

from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "member_count", "created_at")
    search_fields = ("name", "description", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")
    filter_horizontal = ("members",)

    @admin.display(description="Members")
    def member_count(self, obj) -> int:
        return obj.members.count()
