"""ToolStatus.BLOCKED — targets the scope/SSRF guard refused.

A blocked call used to be recorded as ``success`` (the status was unmapped and
the recorder defaulted to success), erasing the only durable evidence that the
guard fired. ``blocked`` is now a first-class status.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("observability", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="toolexecution",
            name="status",
            field=models.CharField(
                choices=[
                    ("running", "Running"),
                    ("success", "Success"),
                    ("error", "Error"),
                    ("timeout", "Timeout"),
                    ("unavailable", "Unavailable"),
                    ("blocked", "Blocked"),
                ],
                default="running",
                max_length=16,
            ),
        ),
    ]
