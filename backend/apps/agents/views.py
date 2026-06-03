"""Agents app: thin DRF wrappers over the engine (tools list + graph topology).

Engine imports are lazy so the project boots/checks without crewai installed.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tools_list(request):
    try:
        from redweaver_engine.tools.registry import ToolRegistry

        report = ToolRegistry().get_availability_report()
    except Exception as exc:  # engine deps unavailable
        return Response(
            {"categories": {}, "total_count": 0, "available_count": 0, "error": str(exc)}
        )
    total = sum(len(v) for v in report.values())
    available = sum(1 for v in report.values() for t in v if t.get("available"))
    return Response(
        {"categories": report, "total_count": total, "available_count": available}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def graph_topology(request):
    target, objective, ssh = None, "comprehensive", None
    run_id = request.query_params.get("run_id")
    if run_id:
        from apps.hunts.models import Run

        run = Run.objects.filter(id=run_id).first()
        if run:
            target, objective, ssh = run.target, run.objective, run.ssh_config

    nodes, edges = [], []
    try:
        from redweaver_engine.crews.bug_hunt.graph import get_graph_topology

        topo = (
            get_graph_topology(target=target, objective=objective, ssh_config=ssh)
            if target
            else get_graph_topology()
        )
        nodes, edges = topo.get("nodes", []), topo.get("edges", [])
    except Exception:
        pass

    return Response(
        {"nodes": nodes, "edges": edges,
         "state": {"current_node": None, "completed_nodes": [], "plan": [], "steps": []}}
    )
