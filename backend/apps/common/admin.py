"""Shared admin utilities: read-only mixin + JSON/pre/thumbnail renderers."""
import json

from django.utils.html import format_html


class ReadOnlyAdminMixin:
    """Machine-written rows: viewable + deletable, never hand-edited/added."""

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


def pretty_json(value) -> str:
    """Render a JSON-serializable value as an indented <pre> block."""
    try:
        text = json.dumps(value, indent=2, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    return format_html(
        '<pre style="max-height:480px;overflow:auto;white-space:pre-wrap;'
        'background:#0b0f14;color:#cfe;padding:8px;border-radius:6px;">{}</pre>',
        text,
    )


def pre_block(text) -> str:
    """Render raw text (stdout/stderr) in a scrollable monospace block."""
    return format_html(
        '<pre style="max-height:480px;overflow:auto;white-space:pre-wrap;'
        'background:#0b0f14;color:#d6e7ff;padding:8px;border-radius:6px;">{}</pre>',
        text or "",
    )
