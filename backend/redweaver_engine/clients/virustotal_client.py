"""VirusTotal API client for URL report."""
import base64
import json
import urllib.error
import urllib.request
from typing import Any, Protocol


class VirusTotalClientProtocol(Protocol):
    """Protocol for VirusTotal URL operations."""

    def get_url_report(self, url: str) -> dict[str, Any]:
        """Get URL report. Raises on API error."""
        ...


class VirusTotalClient:
    """VirusTotal API v3 client (URL report only)."""

    BASE = "https://www.virustotal.com/api/v3"

    def __init__(self, api_key: str) -> None:
        self._api_key = (api_key or "").strip()
        if not self._api_key:
            raise ValueError("VirusTotal API key is required")

    @staticmethod
    def _url_id(url: str) -> str:
        return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")

    def get_url_report(self, url: str) -> dict[str, Any]:
        url_id = self._url_id(url)
        req = urllib.request.Request(
            f"{self.BASE}/urls/{url_id}",
            headers={"x-apikey": self._api_key},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            try:
                err = json.loads(body)
                raise RuntimeError(err.get("error", {}).get("message", body) or str(e)) from e
            except json.JSONDecodeError:
                raise RuntimeError(body or str(e)) from e
