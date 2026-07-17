"""Attack playbook crew: a single red-team operator agent that turns
a run's findings into a practical, staged attack flow with concrete commands,
grounded in the local knowledge base and live web research.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from crewai import Agent, Crew, Process, Task

from redweaver_engine.tools.crewai_adapter import to_crewai_tools

OPERATOR_ROLE = "Red Team Operator"


def build_attack_crew(
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
            tools += to_crewai_tools([t], run_id, "attack")
    try:
        from redweaver_engine.tools.knowledge_query_tool import KnowledgeTool

        tools.append(KnowledgeTool())
    except Exception:
        pass

    agent = Agent(
        role=OPERATOR_ROLE,
        goal=(
            "Turn confirmed findings into a concrete, ethical, lab-only exploitation "
            "playbook: a stage-by-stage attack flow with exact commands and tooling, "
            "grounded in the knowledge base and current public research."
        ),
        backstory=(
            "You are a senior red-team operator and hands-on exploitation specialist. "
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
        "Produce a PROFESSIONAL PENETRATION-TEST ENGAGEMENT REPORT in Markdown for an "
        "authorized engagement, following the PTES structure. It MUST be specific to what "
        "the agents actually found on THIS target and GROUNDED in the RESEARCH CONTEXT "
        "above (per-finding KB techniques, CVE details, public exploits, AND the computed "
        "ENGAGEMENT INTEL: risk score, SSVC decision, EPSS, KEV, exploit availability and "
        "MITRE ATT&CK technique per finding). Quote/adapt the exact commands from the KB "
        "'KB technique' blocks, substituting this target's real host/port/URL. You may "
        "also call knowledge_search / web_search / cvedetails_lookup to dig deeper.\n\n"
        "PRIORITIZE by the SSVC decision + risk score from the ENGAGEMENT INTEL (Act > "
        "Attend > Track* > Track), NOT by CVSS alone — remember only ~2% of CVEs are "
        "exploited in the wild, so KEV and EPSS dominate.\n\n"
        "Required structure:\n"
        "# Penetration Test Engagement — <target>\n"
        "## Executive Summary\n"
        "   - Plain-English overview for leadership: overall risk rating, count of findings "
        "by severity, and the TOP 3 most critical issues (what an attacker could actually do).\n"
        "   - A short **Prioritization** table: | Finding | Severity | Risk | SSVC | EPSS | KEV |\n"
        "## Attack Path (Kill Chain)\n"
        "   - An ordered narrative mapping THIS target's findings across the kill chain "
        "(recon -> initial access -> execution -> privilege escalation -> lateral movement "
        "-> exfiltration), each step tagged with its MITRE ATT&CK technique id+name. "
        "Reference that a MITRE ATT&CK Navigator layer is available for this run.\n"
        "## Findings -> Exploitation  (ONE `### [SSVC:<decision>] [SEVERITY] <finding title>` "
        "subsection PER significant finding, ORDERED by risk) each containing:\n"
        "   - **Risk**: risk score + SSVC decision · **EPSS**: x% · **KEV**: yes/no · "
        "**Exploit availability**: weaponized/PoC/none (from the intel)\n"
        "   - **MITRE ATT&CK**: technique id + name\n"
        "   - **Why**: why it's exploitable (cite the CVE/service + CVSS vector if known)\n"
        "   - **Commands**: ```bash fenced blocks — the ACTUAL commands from the KB "
        "technique blocks, with this target's host/port/URL filled in (nmap, hydra, ffuf, "
        "sqlmap, nuclei, metasploit, curl, etc.)\n"
        "   - **Expected result** / **Verification**\n"
        "   - **KB source**: exact KB filename(s) used (REQUIRED when a KB block exists)\n"
        "   - **References**: CVE/exploit URL(s)\n"
        "## Privilege Escalation & Post-Exploitation — based on the shared KB methodology "
        "blocks; cite their KB filenames (e.g. linux-privesc-methodology.md).\n"
        "## Remediation Roadmap — a PRIORITIZED, time-boxed plan in three buckets mapped to "
        "SSVC: **Immediate (Act)**, **Short-term (Attend)**, **Longer-term (Track)** — each "
        "item the concrete fix (not generic advice) tied to its finding(s).\n"
        "## Cleanup & Notes\n\n"
        "Be specific and command-driven — NO vague advice, NO placeholder hosts. Cite the "
        "KB filename for every technique you use."
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
