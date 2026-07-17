"""Workspaces: top-level container grouping sessions and targets."""
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedUUIDModel


class Workspace(TimeStampedUUIDModel):
    """Replaces legacy ``domain.workspace.Workspace``.

    ``owner_id`` -> owner FK; ``member_ids`` -> members M2M (which also gives
    ``user.workspaces`` reverse access for the User model defined in B1).
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_workspaces",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="workspaces",
    )

    # Report branding (shown on exported reports)
    brand_name = models.CharField(max_length=128, blank=True, default="")
    brand_color = models.CharField(max_length=16, blank=True, default="")
    brand_logo_url = models.URLField(max_length=1024, blank=True, default="")

    def __str__(self) -> str:
        return self.name
