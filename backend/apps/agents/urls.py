"""Agents routes (mounted at /api/): tools list + graph topology."""
from django.urls import path

from .views import graph_topology, tools_list

urlpatterns = [
    path("tools", tools_list, name="tools-list"),
    path("graph", graph_topology, name="graph-topology"),
    path("graph/topology", graph_topology, name="graph-topology-alias"),
]
