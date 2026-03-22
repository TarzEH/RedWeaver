"""Parse user messages to detect scan intent and extract target info."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScanIntent:
    """Detected scan intent from a user message."""

    target: str
    scope: str = ""
    objective: str = "comprehensive"


class ScanIntentParser:
    """Parses user messages to detect scan intent and extract target info.

    Detects when a user message contains a URL/domain combined with a
    scan-related verb, and extracts the target and scan parameters.
    """

    SCAN_VERBS = (
        "scan", "test", "hunt", "check", "audit",
        "run", "start", "investigate",
    )
    SCAN_NOUNS = ("bug", "pentest")

    URL_PATTERN = re.compile(
        r"https?://[^\s]+|(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}",
    )

    def parse(self, text: str) -> ScanIntent | None:
        """Return ScanIntent if the message indicates a scan request, else None.

        A bare URL/domain (the entire message is just a URL) is treated as
        implicit scan intent — this is a pentesting tool, so pasting a URL
        means "scan this".
        """
        text_lower = text.lower().strip()

        url_match = self.URL_PATTERN.search(text_lower)
        if not url_match:
            return None

        target = url_match.group(0).split()[0]
        if not target:
            return None

        # Bare URL: entire message is just a URL/domain -> implicit scan intent
        is_bare_url = text_lower.strip().rstrip("/") == target.rstrip("/")

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
