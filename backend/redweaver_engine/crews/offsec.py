"""OffSec playbook crew: a single offensive-security operator agent that turns
a run's findings into a practical, staged attack flow with concrete commands,
grounded in the local knowledge base and live web research.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from crewai import Agent, Crew, Process, Task

from redweaver_engine.tools.crewai_adapter import to_crewai_tools

OFFSEC_ROLE = "Offensive Security Operator"


def build_offsec_crew(
    llm: Any,
    registry: Any,
    target: str,
    findings: list[dict],
    run_id: str | None = None,
    step_callback: Callable | None = None,
    task_callback: Callable | None = None,
    research_context: str = "",
) -> Crew:
    # Research tools: web search, CVE lookup, and the local knowledge base.
    tools: list = []
    for name in ("web_search", "cvedetails_lookup"):
        t = registry.get_tool(name)
        if t:
            tools += to_crewai_tools([t], run_id, "offsec")
    try:
        from redweaver_engine.tools.knowledge_query_tool import KnowledgeTool

        tools.append(KnowledgeTool())
    except Exception:
        pass

    agent = Agent(
        role=OFFSEC_ROLE,
        goal=(
            "Turn confirmed findings into a concrete, ethical, lab-only exploitation "
            "playbook: a stage-by-stage attack flow with exact commands and tooling, "
            "grounded in the knowledge base and current public research."
        ),
        backstory=(
            "You are a senior red-team operator and OSCP-style exploitation specialist. "
            "You think in kill chains: recon -> initial access -> exploitation -> "
            "privilege escalation -> lateral movement -> exfiltration. For every finding "
            "you cite the precise technique, the exact command(s) to run, the expected "
            "output, and a verification step. You ALWAYS consult the knowledge base "
            "(knowledge_search) and corroborate with web_search / cvedetails before "
            "recommending an exploit. You write for an authorized engagement only."
        ),
        tools=tools,
        llm=llm,
        allow_delegation=False,
        respect_context_window=True,
        max_iter=25,
        verbose=False,
    )

    findings_block = json.dumps(findings, indent=2, default=str)[:9000]
    research_section = ""
    if research_context.strip():
        research_section = (
            "\n\n## RESEARCH CONTEXT (REAL pre-fetched sources — base your "
            "recommendations, commands and References on THESE; cite the KB file / "
            "URL / CVE for each recommendation):\n"
            f"{research_context}\n"
        )
    description = (
        f"Target: {target}\n\n"
        f"Confirmed findings from the automated hunt (analyze these in parallel):\n"
        f"```json\n{findings_block}\n```\n"
        f"{research_section}\n"
        "Produce a PRACTICAL, FINDING-DRIVEN OFFENSIVE PLAYBOOK in Markdown for an "
        "authorized engagement. It MUST be specific to what the agents actually found "
        "on THIS target — every recommendation tied to a real finding and GROUNDED in "
        "the RESEARCH CONTEXT above (the per-finding KB techniques, CVE details and "
        "public exploits). Quote/adapt the exact commands from the KB 'KB technique' "
        "blocks, substituting this target's real host/port/URL for placeholders. You "
        "may also call knowledge_search / web_search / cvedetails_lookup to dig deeper. "
        "Structure:\n"
        "# OffSec Playbook — <target>\n"
        "## Attack Flow Overview — short ordered kill-chain mapping THIS target's "
        "findings to MITRE ATT&CK tactics.\n"
        "## Findings -> Exploitation  (ONE `### [SEVERITY] <finding title>` subsection "
        "PER significant finding) each containing:\n"
        "   - **MITRE ATT&CK**: technique id + name (e.g. T1110 Brute Force)\n"
        "   - **Why**: why it's exploitable (cite the CVE/service)\n"
        "   - **Commands**: ```bash fenced blocks — the ACTUAL commands from the KB "
        "technique blocks above, with this target's host/port/URL filled in (nmap, "
        "hydra, ffuf, sqlmap, nuclei, metasploit, curl, etc.)\n"
        "   - **Expected result** / **Verification**\n"
        "   - **References**: KB filename(s) used + CVE/exploit URL(s)\n"
        "## Privilege Escalation & Post-Exploitation — using the shared KB methodology.\n"
        "## Cleanup & Notes\n\n"
        "Be specific and command-driven — NO vague advice, NO placeholder hosts. "
        "Prioritize by severity. Cite the KB filename for every technique you use."
    )

    task = Task(
        description=description,
        expected_output=(
            "A complete Markdown offensive playbook with an attack-flow overview and "
            "per-stage sections containing exact commands in fenced code blocks, tied to "
            "the findings, with KB and public references."
        ),
        agent=agent,
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
        step_callback=step_callback,
        task_callback=task_callback,
    )
