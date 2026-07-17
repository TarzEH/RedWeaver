"""Parse user messages to detect scan intent (ported verbatim from legacy)."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScanIntent:
    target: str
    scope: str = ""
    objective: str = "comprehensive"


class ScanIntentParser:
    SCAN_VERBS = ("scan", "test", "hunt", "check", "audit", "run", "start", "investigate")
    SCAN_NOUNS = ("bug", "pentest")
    URL_PATTERN = re.compile(
        r"https?://[^\s]+|(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}",
    )

    def parse(self, text: str) -> ScanIntent | None:
        text_lower = (text or "").lower().strip()
        url_match = self.URL_PATTERN.search(text_lower)
        if not url_match:
            return None
        target = url_match.group(0).split()[0]
        if not target:
            return None
        is_bare_url = text_lower.rstrip("/") == target.rstrip("/")
        has_verb = any(v in text_lower for v in self.SCAN_VERBS)
        has_noun = any(n in text_lower for n in self.SCAN_NOUNS)
        if not has_verb and not has_noun and not is_bare_url:
            return None
        objective = "comprehensive"
        if "quick" in text_lower:
            objective = "quick"
        elif "stealth" in text_lower:
            objective = "stealth"
        return ScanIntent(target=target, scope="", objective=objective)
