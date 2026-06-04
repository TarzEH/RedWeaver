"""Finding serializer — shape matches frontend `Finding` type."""
from rest_framework import serializers

from .models import Finding


class FindingSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = Finding
        fields = ("id", "title", "severity", "description", "affected_url",
                  "evidence", "remediation", "agent_source", "tool_used",
                  "cvss_score", "cve_ids", "timestamp",
                  "status", "confidence", "exploitability", "cisa_kev", "epss_score")
        read_only_fields = ("id", "timestamp")


class FindingTriageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ("status",)
