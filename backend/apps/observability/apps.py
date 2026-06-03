from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.observability"

    def ready(self):
        """Wire the engine instrumentation seam to the DB-backed sinks."""
        try:
            from redweaver_engine.tools import instrumentation as instr

            from .publisher import record_and_publish
            from .recorders import tool_recorder

            # Combined sink: EventLog + Channels broadcast + normalized rows.
            instr.set_event_publisher(record_and_publish)
            instr.set_tool_recorder(tool_recorder)
        except Exception:  # engine optional during some mgmt commands
            pass
