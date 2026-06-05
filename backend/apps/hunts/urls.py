"""Run/hunt/session/target routes (mounted at /api/)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .chat_views import ChatView
from .views import (
    HuntViewSet,
    NotificationChannelViewSet,
    RunViewSet,
    ScheduleViewSet,
    SessionViewSet,
    TargetViewSet,
    attack_plan,
    run_ask,
    run_attack_graph,
    run_offsec,
    session_assets,
    session_posture,
)

router = SimpleRouter(trailing_slash=False)
router.register("runs", RunViewSet, basename="run")
router.register("hunts", HuntViewSet, basename="hunt")
router.register("sessions", SessionViewSet, basename="session")
router.register("targets", TargetViewSet, basename="target")
router.register("notification-channels", NotificationChannelViewSet, basename="notification-channel")
router.register("schedules", ScheduleViewSet, basename="schedule")

urlpatterns = [
    path("chat", ChatView.as_view(), name="chat"),
    path("runs/<uuid:run_id>/offsec", run_offsec, name="run-offsec"),
    path("runs/<uuid:run_id>/ask", run_ask, name="run-ask"),
    path("sessions/<uuid:session_id>/assets", session_assets, name="session-assets"),
    path("sessions/<uuid:session_id>/posture", session_posture, name="session-posture"),
    path("runs/<uuid:run_id>/attack-graph", run_attack_graph, name="run-attack-graph"),
    path("attack/plan", attack_plan, name="attack-plan"),
    *router.urls,
]
