"""NotificationChannel — outbound webhook/Slack targets."""
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspaces", "0001_initial"),
        ("hunts", "0003_run_cost_and_task_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationChannel",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=128)),
                ("kind", models.CharField(choices=[("webhook", "Webhook"), ("slack", "Slack")], default="webhook", max_length=16)),
                ("url", models.URLField(max_length=1024)),
                ("events", models.JSONField(blank=True, default=list)),
                ("enabled", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_channels", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_channels", to="workspaces.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
