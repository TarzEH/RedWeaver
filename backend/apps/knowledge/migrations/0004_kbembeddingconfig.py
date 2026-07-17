"""Global singleton KbEmbeddingConfig — UI-editable embedding provider/model.

Lets the embedding provider (OpenAI vs offline HuggingFace), model, and device
be changed from the Settings page without pre-setting env vars. Seeds a single
row from the current env/settings so existing behaviour is preserved.
"""
from django.conf import settings
from django.db import migrations, models


def _seed(apps, schema_editor):
    KbEmbeddingConfig = apps.get_model("knowledge", "KbEmbeddingConfig")
    provider = (getattr(settings, "KB_EMBED_PROVIDER", "openai") or "openai").lower()
    KbEmbeddingConfig.objects.update_or_create(
        id=1,
        defaults={
            "provider": provider,
            "model": getattr(settings, "KB_EMBED_MODEL", "") or "",
            "dimension": int(getattr(settings, "KB_EMBED_DIM", 1536)),
            "device": getattr(settings, "KB_EMBED_DEVICE", "cpu") or "cpu",
        },
    )


def _unseed(apps, schema_editor):
    KbEmbeddingConfig = apps.get_model("knowledge", "KbEmbeddingConfig")
    KbEmbeddingConfig.objects.filter(id=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0003_embedding_dim_from_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbEmbeddingConfig",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(choices=[("openai", "OpenAI"), ("huggingface", "HuggingFace (offline)")], default="openai", max_length=32)),
                ("model", models.CharField(blank=True, default="", max_length=128)),
                ("dimension", models.PositiveIntegerField(default=1536)),
                ("device", models.CharField(default="cpu", max_length=16)),
                ("status", models.CharField(default="idle", max_length=16)),
                ("last_error", models.TextField(blank=True, default="")),
                ("last_indexed_at", models.DateTimeField(blank=True, null=True)),
                ("chunk_count", models.IntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "KB embedding config",
                "verbose_name_plural": "KB embedding config",
            },
        ),
        migrations.RunPython(_seed, _unseed),
    ]
