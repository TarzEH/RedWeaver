"""Serializers for hunts — shapes match the existing frontend contract."""
from rest_framework import serializers

from apps.findings.serializers import FindingSerializer

from .models import Run, Session, Target


def _sid(value) -> str | None:
    return str(value) if value else None


# --------------------------------------------------------------------------- #
# Session / Target
# --------------------------------------------------------------------------- #
class SessionSerializer(serializers.ModelSerializer):
    workspace_id = serializers.SerializerMethodField()
    target_count = serializers.SerializerMethodField()
    hunt_count = serializers.SerializerMethodField()
    finding_count = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = ("id", "name", "description", "workspace_id", "status",
                  "target_count", "hunt_count", "finding_count", "tags", "created_at")
        read_only_fields = ("id", "created_at")

    def get_workspace_id(self, obj):
        return _sid(obj.workspace_id) or ""

    def get_target_count(self, obj) -> int:
        return obj.targets.count()

    def get_hunt_count(self, obj) -> int:
        return obj.runs.count()

    def get_finding_count(self, obj) -> int:
        return obj.findings.count()


class SessionWriteSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Session
        fields = ("id", "name", "description", "workspace_id", "status", "tags")
        read_only_fields = ("id",)

    def create(self, validated):
        wid = validated.pop("workspace_id", None)
        if wid:
            validated["workspace_id"] = wid
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated["created_by"] = request.user
        return super().create(validated)

    def to_representation(self, instance):
        return SessionSerializer(instance, context=self.context).data


_SSH_KEYS = ("ssh_host", "ssh_username", "ssh_password", "ssh_key_path", "ssh_port")


class TargetSerializer(serializers.ModelSerializer):
    session_id = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    class Meta:
        model = Target
        fields = ("id", "name", "target_type", "session_id", "address",
                  "notes", "tags", "created_at")
        read_only_fields = fields

    def get_session_id(self, obj):
        return _sid(obj.session_id) or ""

    def get_address(self, obj) -> str:
        return obj.address_string()


class TargetWriteSerializer(serializers.Serializer):
    name = serializers.CharField()
    target_type = serializers.ChoiceField(
        choices=[c[0] for c in Target._meta.get_field("target_type").choices]
    )
    session_id = serializers.UUIDField(required=False, allow_null=True)
    url = serializers.CharField(required=False, allow_blank=True)
    base_url = serializers.CharField(required=False, allow_blank=True)
    cidr_ranges = serializers.ListField(child=serializers.CharField(), required=False)
    ip = serializers.CharField(required=False, allow_blank=True)
    domain = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    ssh_host = serializers.CharField(required=False, allow_blank=True)
    ssh_username = serializers.CharField(required=False, allow_blank=True)
    ssh_password = serializers.CharField(required=False, allow_blank=True)
    ssh_key_path = serializers.CharField(required=False, allow_blank=True)
    ssh_port = serializers.IntegerField(required=False)

    def create(self, validated):
        config: dict = {}
        for key in ("url", "base_url", "ip", "domain", "cidr_ranges"):
            if validated.get(key):
                config[key] = validated[key]
        ssh = {k[4:]: validated[k] for k in _SSH_KEYS if validated.get(k)}
        if ssh:
            config["ssh_config"] = ssh
        return Target.objects.create(
            name=validated["name"],
            target_type=validated["target_type"],
            session_id=validated.get("session_id"),
            notes=validated.get("notes", ""),
            tags=validated.get("tags", []),
            config=config,
        )

    def update(self, instance, validated):
        for field in ("name", "target_type", "notes", "tags"):
            if field in validated:
                setattr(instance, field, validated[field])
        if "session_id" in validated:
            instance.session_id = validated["session_id"]
        config = dict(instance.config or {})
        for key in ("url", "base_url", "ip", "domain", "cidr_ranges"):
            if validated.get(key):
                config[key] = validated[key]
        ssh = {k[4:]: validated[k] for k in _SSH_KEYS if validated.get(k)}
        if ssh:
            config["ssh_config"] = ssh
        instance.config = config
        instance.save()
        return instance

    def to_representation(self, instance):
        return TargetSerializer(instance, context=self.context).data


# --------------------------------------------------------------------------- #
# Run (a.k.a. Hunt)
# --------------------------------------------------------------------------- #
def _graph_state(run: Run) -> dict:
    base = run.graph_state
    base["steps"] = [
        {
            "agent": s.agent_name,
            "action": s.step_type,
            "result": s.output_summary or s.reasoning_text or "",
            "timestamp": s.created_at.isoformat(),
        }
        for s in run.agent_steps.order_by("sequence")[:800]
    ]
    base["findings"] = FindingSerializer(run.findings.all(), many=True).data
    return base


class RunSummarySerializer(serializers.ModelSerializer):
    run_id = serializers.CharField(source="id", read_only=True)
    hunt_id = serializers.CharField(source="id", read_only=True)
    session_id = serializers.SerializerMethodField()
    workspace_id = serializers.SerializerMethodField()
    session_name = serializers.SerializerMethodField()
    workspace_name = serializers.SerializerMethodField()

    class Meta:
        model = Run
        fields = ("run_id", "target", "status", "created_at",
                  "hunt_id", "session_id", "workspace_id",
                  "session_name", "workspace_name")

    def get_session_id(self, obj):
        return _sid(obj.session_id)

    def get_workspace_id(self, obj):
        return _sid(obj.workspace_id)

    def get_session_name(self, obj):
        return obj.session.name if obj.session_id else None

    def get_workspace_name(self, obj):
        return obj.workspace.name if obj.workspace_id else None


class RunDetailSerializer(RunSummarySerializer):
    graph_state = serializers.SerializerMethodField()

    class Meta(RunSummarySerializer.Meta):
        fields = RunSummarySerializer.Meta.fields + (
            "messages", "graph_state", "scope", "objective",
        )

    def get_graph_state(self, obj):
        return _graph_state(obj)


class HuntSerializer(serializers.ModelSerializer):
    session_id = serializers.SerializerMethodField()
    target_ids = serializers.SerializerMethodField()
    finding_count = serializers.SerializerMethodField()

    class Meta:
        model = Run
        fields = ("id", "session_id", "target_ids", "status", "target",
                  "objective", "finding_count", "created_at",
                  "started_at", "completed_at")

    def get_session_id(self, obj):
        return _sid(obj.session_id) or ""

    def get_target_ids(self, obj):
        return [str(obj.target_obj_id)] if obj.target_obj_id else []

    def get_finding_count(self, obj) -> int:
        return obj.findings.count()


class HuntDetailSerializer(HuntSerializer):
    graph_state = serializers.SerializerMethodField()

    class Meta(HuntSerializer.Meta):
        fields = HuntSerializer.Meta.fields + ("messages", "graph_state", "error_message")

    def get_graph_state(self, obj):
        return _graph_state(obj)


class HuntCreateSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(required=False, allow_null=True)
    target_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    objective = serializers.CharField(required=False, default="comprehensive")
    agent_selection = serializers.ListField(child=serializers.CharField(), required=False)
    timeout_seconds = serializers.IntegerField(required=False, default=900)
    ssh_config = serializers.DictField(required=False)

    def create(self, validated):
        request = self.context.get("request")
        target_ids = validated.get("target_ids") or []
        target_obj = Target.objects.filter(id__in=target_ids).first() if target_ids else None
        session = Session.objects.filter(id=validated["session_id"]).first() \
            if validated.get("session_id") else None
        return Run.objects.create(
            session=session,
            target_obj=target_obj,
            workspace=(session.workspace if session else None),
            created_by=(request.user if request and request.user.is_authenticated else None),
            target=(target_obj.address_string() if target_obj else ""),
            objective=validated.get("objective", "comprehensive"),
            agent_selection=validated.get("agent_selection", []),
            timeout_seconds=validated.get("timeout_seconds", 900),
            ssh_config=validated.get("ssh_config"),
        )

    def to_representation(self, instance):
        return HuntSerializer(instance, context=self.context).data
