"""Run: celery_task_id (for cancellation) + LLM cost/token accounting."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hunts", "0002_run_attack_markdown_run_attack_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="celery_task_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="run",
            name="prompt_tokens",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="run",
            name="completion_tokens",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="run",
            name="total_tokens",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="run",
            name="cost_usd",
            field=models.DecimalField(decimal_places=4, default=0, max_digits=10),
        ),
    ]
