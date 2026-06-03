"""CVE database client using the NVD (NIST) REST API v2.0.

Provides structured CVE lookups by keyword, CVE ID, or vendor/product CPE.
Also supports cvedetails.com URL references for enriched context.

Rate limits (NVD): 5 requests / 30s without API key, 50 with key.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "RedWeaver-BugHunter/1.0 "
    "(+https://github.com/redweaver; security-research)"
)


class CVEDetailsClient:
    """NVD API v2.0 client for CVE lookups with cvedetails.com references."""

    NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    CVEDETAILS_BASE = "https://www.cvedetails.com"

    def __init__(self, nvd_api_key: str = "") -> None:
        self._api_key = (nvd_api_key or "").strip()
        self._last_request: float = 0.0
        # NVD rate limit: 6s between requests without key, 0.6s with key
        self._min_interval = 0.6 if self._api_key else 6.0

    def _throttle(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _nvd_request(self, params: dict[str, str]) -> dict[str, Any]:
        """Make a rate-limited request to the NVD API."""
        self._throttle()
        query = urllib.parse.urlencode(params)
        url = f"{self.NVD_BASE}?{query}"
        headers: dict[str, str] = {"User-Agent": _USER_AGENT}
        if self._api_key:
            headers["apiKey"] = self._api_key
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            logger.warning("NVD API error %s: %s", e.code, body[:200])
            raise RuntimeError(f"NVD API error {e.code}: {body[:200]}") from e

    @staticmethod
    def _parse_cve(vuln: dict[str, Any]) -> dict[str, Any]:
        """Parse a single NVD vulnerability entry into a flat dict."""
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "")

        # Extract English description
        descriptions = cve.get("descriptions", [])
        description = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"),
            descriptions[0]["value"] if descriptions else "",
        )

        # Extract CVSS score — prefer v3.1, fall back to v3.0, then v2
        cvss_score: float | None = None
        cvss_severity: str = ""
        cvss_vector: str = ""
        metrics = cve.get("metrics", {})
        for version_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            entries = metrics.get(version_key, [])
            if entries:
                data = entries[0].get("cvssData", {})
                cvss_score = data.get("baseScore")
                cvss_severity = (
                    data.get("baseSeverity", "")
                    or entries[0].get("baseSeverity", "")
                ).upper()
                cvss_vector = data.get("vectorString", "")
                break

        # Extract weaknesses (CWE IDs)
        cwes: list[str] = []
        for weakness in cve.get("weaknesses", []):
            for desc in weakness.get("description", []):
                val = desc.get("value", "")
                if val.startswith("CWE-"):
                    cwes.append(val)

        # Extract references
        refs = [r.get("url", "") for r in cve.get("references", [])[:5]]

        # CISA KEV data (Known Exploited Vulnerabilities)
        cisa_exploit_add = cve.get("cisaExploitAdd")
        cisa_action_due = cve.get("cisaActionDue")

        # Build cvedetails.com reference URL
        cvedetails_url = f"{CVEDetailsClient.CVEDETAILS_BASE}/cve/{cve_id}/"

        return {
            "cve_id": cve_id,
            "description": description,
            "cvss_score": cvss_score,
            "cvss_severity": cvss_severity,
            "cvss_vector": cvss_vector,
            "cwes": cwes,
            "published": cve.get("published", ""),
            "last_modified": cve.get("lastModified", ""),
            "references": refs,
            "cvedetails_url": cvedetails_url,
            "cisa_known_exploited": cisa_exploit_add is not None,
            "cisa_action_due": cisa_action_due,
        }

    def search_cves(
        self,
        keyword: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search CVEs by keyword (technology, vendor, product name).

        Example: search_cves("hmailserver") -> all hMailServer CVEs.
        """
        params: dict[str, str] = {
            "keywordSearch": keyword,
            "resultsPerPage": str(min(max_results, 100)),
        }
        data = self._nvd_request(params)
        total = data.get("totalResults", 0)
        vulns = data.get("vulnerabilities", [])
        results = [self._parse_cve(v) for v in vulns]
        logger.info(
            "NVD keyword search '%s': %d/%d results", keyword, len(results), total
        )
        return results

    def get_cve(self, cve_id: str) -> dict[str, Any] | None:
        """Look up a single CVE by ID (e.g. CVE-2024-21413).

        Returns parsed CVE dict or None if not found.
        """
        params: dict[str, str] = {"cveId": cve_id}
        try:
            data = self._nvd_request(params)
        except RuntimeError:
            return None
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return None
        return self._parse_cve(vulns[0])

    def get_cves_by_cpe(
        self,
        vendor: str,
        product: str = "",
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Search CVEs by CPE vendor/product name.

        Uses the virtualMatchString parameter to match CPE patterns.
        Example: get_cves_by_cpe("hmailserver", "hmailserver")
        """
        cpe_parts = ["cpe", "2.3", "a", vendor.lower()]
        if product:
            cpe_parts.append(product.lower())
        cpe_match = ":".join(cpe_parts)

        params: dict[str, str] = {
            "virtualMatchString": cpe_match,
            "resultsPerPage": str(min(max_results, 100)),
        }
        try:
            data = self._nvd_request(params)
        except RuntimeError as e:
            # CPE match may fail — fall back to keyword search
            logger.warning("CPE search failed, falling back to keyword: %s", e)
            return self.search_cves(vendor if not product else product, max_results)

        vulns = data.get("vulnerabilities", [])
        return [self._parse_cve(v) for v in vulns]

    def get_vendor_cves(
        self,
        vendor_name: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Convenience: get all CVEs for a vendor by name.

        Tries CPE-based search first, falls back to keyword search.
        """
        results = self.get_cves_by_cpe(vendor_name, max_results=max_results)
        if not results:
            results = self.search_cves(vendor_name, max_results=max_results)
        return results
