from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.observability"

    def ready(self):
        """Wire the engine instrumentation seam to the DB-backed sinks."""
        try:
            from redweaver_engine.tools import instrumentation as instr

            from .publisher import publish
            from .recorders import tool_recorder

            instr.set_event_publisher(publish)
            instr.set_tool_recorder(tool_recorder)
        except Exception:  # engine optional during some mgmt commands
            pass
