"""URLScan.io API client: submit URL and fetch result."""
import json
import time
import urllib.error
import urllib.request
from typing import Any


class URLScanClient:
    """URLScan.io API v1 client."""

    BASE = "https://urlscan.io/api/v1"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = (api_key or "").strip()
        self._headers = {"Content-Type": "application/json"}
        if self._api_key:
            self._headers["API-Key"] = self._api_key

    def submit(self, url: str, visibility: str = "private") -> dict[str, Any]:
        """Submit URL for scanning. Returns submission response with uuid and result URL."""
        data = json.dumps({"url": url, "visibility": visibility}).encode()
        req = urllib.request.Request(
            f"{self.BASE}/scan/",
            data=data,
            headers=self._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            try:
                err = json.loads(body)
                msg = err.get("message", err.get("description", body))
                raise RuntimeError(msg) from e
            except json.JSONDecodeError:
                raise RuntimeError(body or str(e)) from e

    def get_result(self, uuid: str) -> dict[str, Any]:
        """Get scan result by uuid. Raises if not ready (404) or error."""
        req = urllib.request.Request(
            f"{self.BASE}/result/{uuid}/",
            headers=self._headers,
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def submit_and_wait(
        self,
        url: str,
        visibility: str = "private",
        poll_interval: float = 5.0,
        max_wait: float = 120.0,
    ) -> dict[str, Any]:
        """Submit URL, poll until result ready, return result plus submission metadata."""
        sub = self.submit(url, visibility)
        uuid = sub.get("uuid")
        if not uuid:
            raise RuntimeError("Submission did not return uuid")
        api_url = sub.get("api", f"{self.BASE}/result/{uuid}/")
        result_url = sub.get("result", f"https://urlscan.io/result/{uuid}/")
        # Wait a bit before first poll
        time.sleep(min(10, poll_interval * 2))
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            try:
                result = self.get_result(uuid)
                result["_submission"] = {"uuid": uuid, "result_url": result_url, "api": api_url}
                result["_screenshot_url"] = f"https://urlscan.io/screenshots/{uuid}.png"
                return result
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    time.sleep(poll_interval)
                    continue
                raise
        raise TimeoutError(f"URLScan result for {uuid} not ready within {max_wait}s")
