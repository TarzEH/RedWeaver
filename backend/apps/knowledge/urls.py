"""Knowledge routes (mounted at /api/)."""
from django.urls import path

from .views import (
    embedding_config,
    knowledge_ask,
    knowledge_categories,
    knowledge_document,
    knowledge_files,
    knowledge_health,
    knowledge_query,
    reindex_knowledge,
)

urlpatterns = [
    path("knowledge/health", knowledge_health, name="knowledge-health"),
    path("knowledge/query", knowledge_query, name="knowledge-query"),
    path("knowledge/categories", knowledge_categories, name="knowledge-categories"),
    path("knowledge/files", knowledge_files, name="knowledge-files"),
    path("knowledge/document", knowledge_document, name="knowledge-document"),
    path("knowledge/ask", knowledge_ask, name="knowledge-ask"),
    path("knowledge/embedding-config", embedding_config, name="knowledge-embedding-config"),
    path("knowledge/reindex", reindex_knowledge, name="knowledge-reindex"),
]
