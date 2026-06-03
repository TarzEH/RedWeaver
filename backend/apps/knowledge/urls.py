"""Knowledge routes (mounted at /api/)."""
from django.urls import path

from .views import knowledge_health, knowledge_query

urlpatterns = [
    path("knowledge/health", knowledge_health, name="knowledge-health"),
    path("knowledge/query", knowledge_query, name="knowledge-query"),
]
