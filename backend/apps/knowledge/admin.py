"""Admin registrations for the knowledge app."""
from django.contrib import admin

from .models import KbEmbeddingConfig


@admin.register(KbEmbeddingConfig)
class KbEmbeddingConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "dimension", "device", "status",
                    "chunk_count", "last_indexed_at")
    readonly_fields = ("dimension", "status", "last_error", "last_indexed_at",
                       "chunk_count", "updated_at")
