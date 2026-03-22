"""HTTP API tools: VirusTotal URL check, URLScan.io submit."""
from typing import Any

from app.clients.virustotal_client import VirusTotalClient
from app.clients.urlscan_client import URLScanClient
from app.tools.base import BugHuntTool, ToolCategory


class VirusTotalURLCheckTool:
    """VirusTotal URL report tool. Requires virustotal_api_key."""

    name = "virustotal_url_check"
    description = "Check a URL against VirusTotal; returns detection count, permalink, and summary."
    category = ToolCategory.HTTP_API

    def is_available(self) -> bool:
        return True  # Always available if constructed (key validated in __init__)

    def __init__(self, api_key: str) -> None:
        if not (api_key or "").strip():
            raise ValueError("VirusTotal API key required")
        self._client = VirusTotalClient(api_key.strip())

    def run(self, target: str, scope: str = "", options: dict[str, Any] | None = None) -> str | dict[str, Any]:
        options = options or {}
        url = (target or "").strip()
        if not url:
            return {"error": "target URL is required"}
        try:
            data = self._client.get_url_report(url)
        except Exception as e:
            return {"error": str(e)}
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats") or {}
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        total = sum(stats.values()) or 1
        permalink = attrs.get("permalink", "")
        summary = "clean" if (malicious == 0 and suspicious == 0) else f"{malicious} malicious, {suspicious} suspicious"
        return {
            "url": url,
            "detections": f"{malicious}/{total}",
            "summary": summary,
            "permalink": permalink,
        }

    async def arun(self, target: str, scope: str = "", options: dict[str, Any] | None = None) -> str | dict[str, Any]:
        return self.run(target, scope, options)


class URLScanSubmitTool:
    """URLScan.io submit and wait for result. Web specialist only; enforce scope."""

    name = "urlscan_submit"
    description = "Submit a URL to URLScan.io for analysis; returns screenshot URL, result link, and page info. Use only for in-scope URLs."
    category = ToolCategory.HTTP_API

    def is_available(self) -> bool:
        return True

    def __init__(self, api_key: str = "") -> None:
        self._client = URLScanClient(api_key)

    def run(self, target: str, scope: str = "", options: dict[str, Any] | None = None) -> str | dict[str, Any]:
        options = options or {}
        url = (target or "").strip()
        if not url:
            return {"error": "target URL is required"}
        visibility = (options.get("visibility") or "private") if options else "private"
        poll_interval = float(options.get("poll_interval", 5.0))
        max_wait = float(options.get("max_wait", 90.0))
        try:
            result = self._client.submit_and_wait(url, visibility=visibility, poll_interval=poll_interval, max_wait=max_wait)
        except TimeoutError as e:
            return {"error": str(e), "message": "Scan did not complete in time"}
        except Exception as e:
            return {"error": str(e)}
        sub = result.get("_submission", {})
        screenshot_url = result.get("_screenshot_url", "")
        page = result.get("page", {}) or {}
        return {
            "url": url,
            "result_url": sub.get("result_url", ""),
            "screenshot_url": screenshot_url,
            "visibility": result.get("task", {}).get("visibility", visibility),
            "domain": page.get("domain", ""),
        }

    async def arun(self, target: str, scope: str = "", options: dict[str, Any] | None = None) -> str | dict[str, Any]:
        return self.run(target, scope, options)
