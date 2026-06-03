"""Workspace CRUD (scoped to the requesting user)."""
from django.db.models import Q
from rest_framework import viewsets

from .models import Workspace
from .serializers import WorkspaceSerializer


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    queryset = Workspace.objects.all()

    def get_queryset(self):
        user = self.request.user
        return (
            Workspace.objects.filter(Q(owner=user) | Q(members=user))
            .distinct()
            .prefetch_related("members")
        )

    def perform_create(self, serializer):
        ws = serializer.save(owner=self.request.user)
        ws.members.add(self.request.user)
