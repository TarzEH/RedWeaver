"""CVE database lookup tool using the NVD API via CVEDetailsClient.

Provides agents with structured CVE intelligence: keyword search, single CVE
lookup, and vendor-based queries — all returning CVSS scores, descriptions,
references, and CISA KEV (Known Exploited Vulnerabilities) status.
"""
import logging
import re
from typing import Any

from app.clients.cvedetails_client import CVEDetailsClient
from app.tools.base import ToolCategory

logger = logging.getLogger(__name__)

_CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


class CVEDetailsLookupTool:
    """Look up known CVEs from the NVD database.

    Routes automatically based on input:
    - CVE ID (e.g. "CVE-2024-21413") → single CVE detail lookup
    - options={'vendor_id': 'hmailserver'} → vendor-based CVE search
    - Any other string → keyword search
    """

    name = "cvedetails_lookup"
    description = (
        "Look up known CVEs from the NVD (National Vulnerability Database). "
        "Pass a technology/vendor name as target for keyword search (e.g. 'Apache 2.4.49'), "
        "or a CVE ID like 'CVE-2024-21413' for detailed lookup. "
        "Use options={'vendor': 'hmailserver'} for vendor-specific CVE search. "
        "Returns CVE IDs, CVSS scores, descriptions, and CISA KEV exploit status."
    )
    category = ToolCategory.VULNERABILITY

    def __init__(self, nvd_api_key: str = "") -> None:
        self._client = CVEDetailsClient(nvd_api_key)

    def is_available(self) -> bool:
        return True

    def run(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        target = (target or "").strip()
        options = options or {}

        if not target and not options:
            return {"error": "target or options required"}

        try:
            # Route 1: Single CVE lookup
            if target and _CVE_PATTERN.match(target):
                return self._lookup_cve(target.upper())

            # Route 2: Vendor-based search
            vendor = options.get("vendor", "")
            if vendor:
                return self._search_vendor(str(vendor), options)

            # Route 3: Keyword search (default)
            if target:
                return self._search_keyword(target, options)

            return {"error": "provide a target keyword or options={'vendor': '...'}"}

        except Exception as e:
            logger.exception("CVE lookup failed: %s", e)
            return {"error": str(e)}

    async def arun(
        self,
        target: str,
        scope: str = "",
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        return self.run(target, scope, options)

    def _lookup_cve(self, cve_id: str) -> dict[str, Any]:
        """Look up a single CVE by ID."""
        result = self._client.get_cve(cve_id)
        if not result:
            return {"error": f"CVE {cve_id} not found in NVD"}
        return {
            "query_type": "cve_detail",
            "cve_id": cve_id,
            "result": result,
        }

    def _search_vendor(
        self, vendor: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Search CVEs for a specific vendor."""
        max_results = int(options.get("max_results", 20))
        product = str(options.get("product", ""))
        if product:
            results = self._client.get_cves_by_cpe(vendor, product, max_results)
        else:
            results = self._client.get_vendor_cves(vendor, max_results)
        return self._format_results(
            results,
            query_type="vendor_search",
            query=f"vendor={vendor}" + (f", product={product}" if product else ""),
        )

    def _search_keyword(
        self, keyword: str, options: dict[str, Any]
    ) -> dict[str, Any]:
        """Search CVEs by keyword."""
        max_results = int(options.get("max_results", 20))
        results = self._client.search_cves(keyword, max_results)
        return self._format_results(
            results, query_type="keyword_search", query=keyword
        )

    @staticmethod
    def _format_results(
        results: list[dict[str, Any]],
        query_type: str,
        query: str,
    ) -> dict[str, Any]:
        """Format CVE results with summary statistics."""
        severity_counts: dict[str, int] = {}
        exploited_count = 0
        for r in results:
            sev = r.get("cvss_severity", "UNKNOWN") or "UNKNOWN"
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            if r.get("cisa_known_exploited"):
                exploited_count += 1

        return {
            "query_type": query_type,
            "query": query,
            "total_results": len(results),
            "severity_summary": severity_counts,
            "cisa_known_exploited_count": exploited_count,
            "cves": results,
        }
