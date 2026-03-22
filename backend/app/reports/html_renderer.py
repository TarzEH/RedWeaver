"""Render ReportData into a professional HTML vulnerability report."""

from __future__ import annotations

import os
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.reports.generator import ReportData


_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _get_jinja_env() -> Environment:
    """Create a Jinja2 environment with the templates directory."""
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=True,
    )


def _severity_color(severity: str) -> str:
    """Map severity to CSS color."""
    return {
        "critical": "#ff1744",
        "high": "#ff6d00",
        "medium": "#ffc400",
        "low": "#00c853",
        "info": "#00b0ff",
    }.get(severity.lower(), "#90a4ae")


def _severity_bg(severity: str) -> str:
    """Map severity to background color (muted)."""
    return {
        "critical": "rgba(255,23,68,0.15)",
        "high": "rgba(255,109,0,0.15)",
        "medium": "rgba(255,196,0,0.15)",
        "low": "rgba(0,200,83,0.15)",
        "info": "rgba(0,176,255,0.15)",
    }.get(severity.lower(), "rgba(144,164,174,0.1)")


def _risk_color(rating: str) -> str:
    """Map risk rating to color."""
    return {
        "Critical": "#ff1744",
        "High": "#ff6d00",
        "Medium": "#ffc400",
        "Low": "#00c853",
        "Informational": "#00b0ff",
    }.get(rating, "#90a4ae")


def render_html_report(report_data: ReportData) -> str:
    """Render a ReportData object into a full HTML report string."""
    env = _get_jinja_env()
    env.globals.update({
        "severity_color": _severity_color,
        "severity_bg": _severity_bg,
        "risk_color": _risk_color,
    })
    template = env.get_template("report.html")
    return template.render(report=report_data)
