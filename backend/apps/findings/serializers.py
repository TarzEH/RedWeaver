"""Finding serializer — shape matches frontend `Finding` type."""
from rest_framework import serializers

from .models import AttackChain, Finding, FindingActivity, FindingComment


class FindingSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    risk_score = serializers.SerializerMethodField()
    risk_decision = serializers.SerializerMethodField()
    assignee_email = serializers.SerializerMethodField()

    class Meta:
        model = Finding
        fields = ("id", "title", "severity", "description", "affected_url",
                  "evidence", "remediation", "agent_source", "tool_used",
                  "cvss_score", "cve_ids", "timestamp",
                  "status", "confidence", "exploitability", "cisa_kev", "epss_score",
                  "risk_score", "risk_decision", "assignee", "assignee_email")
        read_only_fields = ("id", "timestamp")

    def _risk(self, obj):
        from .risk import risk_for_finding
        return risk_for_finding(obj)

    def get_risk_score(self, obj):
        return self._risk(obj)["risk_score"]

    def get_risk_decision(self, obj):
        return self._risk(obj)["decision"]

    def get_assignee_email(self, obj):
        return obj.assignee.email if obj.assignee_id else None


class FindingTriageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Finding
        fields = ("status", "assignee")


class FindingCommentSerializer(serializers.ModelSerializer):
    author_email = serializers.SerializerMethodField()

    class Meta:
        model = FindingComment
        fields = ("id", "body", "author_email", "created_at")
        read_only_fields = ("id", "author_email", "created_at")

    def get_author_email(self, obj):
        return obj.author.email if obj.author_id else None


class FindingActivitySerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = FindingActivity
        fields = ("id", "action", "detail", "actor_email", "created_at")

    def get_actor_email(self, obj):
        return obj.actor.email if obj.actor_id else None


class AttackChainSerializer(serializers.ModelSerializer):
    finding_ids = serializers.SerializerMethodField()

    class Meta:
        model = AttackChain
        fields = ("id", "name", "description", "severity", "steps", "finding_ids", "created_at")

    def get_finding_ids(self, obj):
        return [str(f.id) for f in obj.findings.all()]
