"""Finding.epss_score — EPSS exploit probability for real-world prioritization."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("findings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="finding",
            name="epss_score",
            field=models.FloatField(blank=True, null=True, help_text="EPSS exploit probability 0..1"),
        ),
    ]
