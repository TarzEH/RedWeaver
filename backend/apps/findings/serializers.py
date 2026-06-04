"""Finding serializer — shape matches frontend `Finding` type."""
from rest_framework import serializers

from .models import Finding


class FindingSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    risk_score = serializers.SerializerMethodField()
    risk_decision = serializers.SerializerMethodField()

    class Meta:
        model = Finding
        fields = ("id", "title", "severity", "description", "affected_url",
                  "evidence", "remediation", "agent_source", "tool_used",
                  "cvss_score", "cve_ids", "timestamp",
                  "status", "confidence", "exploitability", "cisa_kev", "epss_score",
                  "risk_score", "risk_decision")
        read_only_fields = ("id", "timestamp")

    def _risk(self, obj):
        from .risk import risk_for_finding
        return risk_for_finding(obj)

    def get_risk_score(self, obj):
        return self._risk(obj)["risk_score"]

    def get_risk_decision(self, obj):
        return self._risk(obj)["decision"]


class FindingTriageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ("status",)
