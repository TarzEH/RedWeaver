"""Add an HNSW ANN index on KbChunk.embedding for fast cosine retrieval.

Replaces the brute-force sequential scan kb_search did on every query (and
~20x per OffSec playbook). HNSW gives high-recall approximate nearest-neighbour
lookups that stay fast as the corpus grows.
"""
from django.db import migrations
from pgvector.django import HnswIndex


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="kbchunk",
            index=HnswIndex(
                name="kbchunk_emb_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
