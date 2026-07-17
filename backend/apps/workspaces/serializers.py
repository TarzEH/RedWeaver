"""Workspace serializer — shape matches frontend WorkspaceResponse."""
from rest_framework import serializers

from .models import Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    owner_id = serializers.SerializerMethodField()
    member_ids = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ("id", "name", "description", "owner_id", "member_ids", "created_at")
        read_only_fields = ("id", "owner_id", "member_ids", "created_at")

    def get_owner_id(self, obj):
        return str(obj.owner_id) if obj.owner_id else ""

    def get_member_ids(self, obj):
        return [str(u.id) for u in obj.members.all()]
