"""Enterprise HTML report generation for RedWeaver.

Provides:
- ReportData model for structured report data
- generate_report_data() for aggregating hunt results
- render_html_report() for Jinja2 HTML rendering
"""

from redweaver_engine.reports.generator import ReportData, generate_report_data
from redweaver_engine.reports.html_renderer import render_html_report

__all__ = ["ReportData", "generate_report_data", "render_html_report"]
