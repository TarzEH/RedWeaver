"""Report template: knowledge service first, bundled Markdown fallback for report_writer."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_BUNDLED_TEMPLATE = Path(__file__).resolve().parent / "config" / "report_template.md"


def _load_bundled_template() -> str:
    try:
        text = _BUNDLED_TEMPLATE.read_text(encoding="utf-8")
        if text.strip():
            logger.info("Loaded bundled report template from %s", _BUNDLED_TEMPLATE)
            return text
    except OSError as e:
        logger.debug("Bundled report template not readable: %s", e)
    return ""


def fetch_report_template() -> str:
    """Return a structural Markdown template for the report_writer task.

    Tries the knowledge service API first; if unavailable or empty, uses the
    bundled ``config/report_template.md`` shipped with the app (Docker copies ``app/`` only).
    """
    try:
        import httpx

        url = os.environ.get("KNOWLEDGE_SERVICE_URL", "http://knowledge:8100")
        resp = httpx.post(
            f"{url}/query",
            json={"query": "report template structure", "category": "reporting", "top_k": 1},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                content = results[0].get("content", "") or ""
                if content.strip():
                    logger.info("Fetched report template from knowledge service")
                    return content
    except Exception as e:
        logger.info("Report template not available from knowledge service: %s", e)

    return _load_bundled_template()
