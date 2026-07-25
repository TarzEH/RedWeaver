from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hunts", "0006_run_attack_focus"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="budget_usd",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Stop the hunt once estimated LLM spend reaches this. Empty = no limit."
                ),
                max_digits=10,
                null=True,
            ),
        ),
    ]
