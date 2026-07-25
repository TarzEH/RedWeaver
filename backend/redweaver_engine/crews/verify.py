"""Adversarial verification crew: a single skeptic that tries to refute findings.

The hunt agents are incentivised to report; nothing in the pipeline is
incentivised to say "that is not real". This crew is that counterweight — it is
prompted to *refute*, is given only the evidence the finding actually carries,
and must default to refuting when the evidence does not stand on its own.

It runs after the hunt, over the persisted findings, so it can never disturb
the hunt itself. Its output feeds :mod:`apps.findings.verification`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

VERIFIER_ROLE = "Findings Verification Specialist"


class Verdict(BaseModel):
    """One finding, judged."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="The finding title, copied EXACTLY from the input")
    verdict: str = Field(
        default="uncertain",
        description="One of: confirmed (evidence supports it), refuted (it is a false "
                    "positive), uncertain (evidence is insufficient either way)",
    )
    confidence: float = Field(
        default=0.0,
        description="0.0-1.0: how sure you are OF YOUR VERDICT, not of the finding",
    )
    reason: str = Field(
        default="",
        description="One or two sentences citing the specific evidence that drove the verdict",
    )


class VerificationResult(BaseModel):
    """The verifier's judgement over a batch of findings."""

    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict] = Field(
        default_factory=list,
        description="Exactly one verdict per finding supplied, in the same order",
    )


#: Fields the verifier is allowed to see. Anything persuasive-but-unevidenced
#: (remediation prose, severity labels) is deliberately withheld so the model
#: judges the evidence rather than the confidence of the writing.
_VERIFIABLE_FIELDS = (
    "title", "description", "affected_url", "evidence", "tool_used", "cve_ids", "cvss_score",
)


def findings_payload(findings: list[dict]) -> list[dict]:
    """Reduce findings to the evidence-bearing fields the verifier may see."""
    payload = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        item = {k: finding.get(k) for k in _VERIFIABLE_FIELDS if finding.get(k) not in (None, "")}
        if item.get("title"):
            payload.append(item)
    return payload


def build_verify_crew(
    llm: Any,
    findings: list[dict],
    target: str = "",
    run_id: str | None = None,
    step_callback: Callable | None = None,
    task_callback: Callable | None = None,
) -> Any:
    """Build the verification crew for one batch of findings."""
    from crewai import Agent, Crew, Process, Task

    agent = Agent(
        role=VERIFIER_ROLE,
        goal=(
            "Refute every finding you can. Report a finding as confirmed ONLY when the "
            "evidence attached to it independently proves the claim."
        ),
        backstory=(
            "You are the reviewer who signs off penetration-test reports before they reach "
            "a client, and you have been burned by scanner noise. You have seen 'SQL "
            "injection' raised on a 500 error, 'outdated software' raised on a banner that "
            "was never checked against a version, and CVEs attached to services that do not "
            "run them. You do not re-scan and you do not speculate about what a tool might "
            "have found — you judge ONLY the evidence in front of you. A confident "
            "description with no supporting tool output is exactly the case you exist to "
            "catch. When the evidence does not stand on its own, you refute."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        respect_context_window=True,
        max_iter=3,
        verbose=False,
    )

    payload = findings_payload(findings)
    description = (
        f"Target: {target or 'unspecified'}\n\n"
        "Judge each of the following findings produced by an automated hunt. For EVERY "
        "finding, return exactly one verdict object, copying the `title` field VERBATIM "
        "so the verdict can be matched back.\n\n"
        "Decision rules:\n"
        "- `refuted`  — the evidence does not support the claim, contradicts it, is empty, "
        "or is generic tool chatter. A claim asserted only in the description with no "
        "evidence is refuted.\n"
        "- `confirmed` — the evidence field itself demonstrates the issue (a matching "
        "banner/version, the actual injected payload and response, the exposed content).\n"
        "- `uncertain` — the evidence is partial: real output, but not enough to prove the "
        "specific claim. Use this rather than guessing.\n\n"
        "`confidence` is how sure you are of YOUR VERDICT (0.0-1.0), not how severe or how "
        "real the finding is. Be strict: a CVE id with no version evidence tying it to this "
        "host is not proof.\n\n"
        f"Findings:\n```json\n{json.dumps(payload, indent=2, default=str)[:60000]}\n```"
    )

    task = Task(
        description=description,
        expected_output=(
            "A VerificationResult with one verdict per supplied finding: the exact title, "
            "a verdict of confirmed/refuted/uncertain, a 0.0-1.0 confidence in that verdict, "
            "and a one-sentence reason citing the evidence."
        ),
        agent=agent,
        output_pydantic=VerificationResult,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        step_callback=step_callback,
        task_callback=task_callback,
    )


def extract_verdicts(result: Any) -> list[dict]:
    """Pull the verdict list out of a crew result, tolerating shape drift."""
    candidates = (
        getattr(result, "pydantic", None),
        getattr(result, "json_dict", None),
        result,
    )
    for candidate in candidates:
        if candidate is None:
            continue
        verdicts = getattr(candidate, "verdicts", None)
        if verdicts is None and isinstance(candidate, dict):
            verdicts = candidate.get("verdicts")
        if not verdicts:
            continue
        out = []
        for verdict in verdicts:
            if isinstance(verdict, dict):
                out.append(verdict)
            elif hasattr(verdict, "model_dump"):
                out.append(verdict.model_dump())
        if out:
            return out

    raw = getattr(result, "raw", None)
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
        except ValueError:
            logger.warning("Verifier returned unparseable output; no verdicts applied")
            return []
        if isinstance(data, dict) and isinstance(data.get("verdicts"), list):
            return [v for v in data["verdicts"] if isinstance(v, dict)]
    return []
