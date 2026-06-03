"""Headless-Chromium screenshot tool (Playwright).

Engine-side (no Django): writes the PNG to SCREENSHOTS_DIR/<run_id>/<uuid>.png
and emits a ``screenshot`` event carrying the media-relative path + metadata.
The Django recorder turns that event into a Screenshot row.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from redweaver_engine.tools import instrumentation as instr
from redweaver_engine.tools.base import ToolCategory


class ScreenshotTool:
    name = "screenshot_capture"
    description = (
        "Capture a full-page PNG screenshot of an in-scope http(s) URL using "
        "headless Chromium. Use on discovered live hosts, admin/login panels, "
        "and finding-affected URLs to document visual evidence."
    )
    category = ToolCategory.BROWSER

    def is_available(self) -> bool:
        try:
            import playwright  # noqa: F401
        except Exception:
            return False
        return True

    def _base_dir(self) -> str:
        return (
            os.environ.get("SCREENSHOTS_DIR")
            or os.environ.get("SCREENSHOT_DIR")
            or "/app/media/screenshots"
        )

    def run(self, target: str, scope: str = "", options: dict | None = None) -> Any:
        url = (target or "").strip()
        if not url.startswith(("http://", "https://")):
            return {"error": "screenshot target must be an http(s) URL", "available": True}

        run_id, agent = instr.get_run_context()
        base = self._base_dir()
        media_root = os.path.dirname(base.rstrip("/"))  # e.g. /app/media
        out_dir = os.path.join(base, str(run_id or "adhoc"))
        os.makedirs(out_dir, exist_ok=True)
        fpath = os.path.join(out_dir, f"{uuid.uuid4().hex}.png")
        rel = os.path.relpath(fpath, media_root)  # screenshots/<run>/<uuid>.png

        try:
            from playwright.sync_api import sync_playwright

            timeout_ms = int(
                (options or {}).get("timeout", os.environ.get("SCREENSHOT_TIMEOUT_SEC", 30))
            ) * 1000
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                page = browser.new_page()
                resp = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                title = page.title()
                final_url = page.url
                http_status = resp.status if resp else None
                page.screenshot(path=fpath, full_page=True)
                viewport = page.viewport_size or {}
                browser.close()
        except Exception as e:  # noqa: BLE001
            return {"error": f"screenshot failed: {e}", "available": True}

        size = os.path.getsize(fpath) if os.path.exists(fpath) else 0
        data = {
            "url": url, "final_url": final_url, "path": rel,
            "page_title": title, "http_status": http_status,
            "width": viewport.get("width"), "height": viewport.get("height"),
            "bytes": size, "agent": agent, "tool": self.name,
        }
        instr.publish_event(run_id, "screenshot", data, agent=agent)
        return {
            "status": "captured", "url": url, "page_title": title,
            "http_status": http_status, "path": rel,
        }

    async def arun(self, target: str, scope: str = "", options: dict | None = None) -> Any:
        return self.run(target, scope, options)
