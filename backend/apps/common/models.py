"""Shared abstract base model for every RedWeaver entity."""
import uuid

from django.db import models
from django.utils import timezone


class TimeStampedUUIDModel(models.Model):
    """UUID primary key + created/updated timestamps.

    Mirrors the legacy ``domain.base.BaseEntity`` (id/created_at/updated_at)
    so the API surface stays stable across the FastAPI -> Django migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
