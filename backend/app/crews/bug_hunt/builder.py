"""CrewAI factory: YAML-backed agents/tasks + Python wiring (tools, callbacks, Crew)."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")

from crewai import Agent, Crew, Process, Task

from app.crews.bug_hunt.callbacks import CrewAIEventBridge
from app.crews.bug_hunt.config_loader import (
    get_agent_prompt_dicts,
    get_task_description_templates,
    validate_configs,
)
from app.crews.bug_hunt.selection import SSH_AGENTS, select_agent_names
from app.crews.bug_hunt.template import fetch_report_template
from app.crews.bug_hunt.schemas import (
    CrawlerResult,
    ExploitAnalysisResult,
    FuzzerResult,
    HuntReport,
    PostExploitResult,
    PrivEscResult,
    ReconResult,
    TunnelPivotResult,
    VulnScanResult,
    WebSearchResult,
)
from app.tools.crewai_adapter import to_crewai_tools
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Fail fast on import if configs are broken
validate_configs()


class CrewFactory:
    """Creates the CrewAI agent hierarchy for a hunt from YAML + runtime selection."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm: Any,
        embedder_config: dict[str, Any] | None = None,
    ) -> None:
        self._registry = tool_registry
        self._llm = llm
        self._embedder_config = embedder_config
        self._agent_prompts = get_agent_prompt_dicts()
        self._task_templates = get_task_description_templates()

    def create_crew(
        self,
        target: str,
        scope: str = "",
        objective: str = "comprehensive",
        ssh_config: dict[str, Any] | None = None,
        step_callback: Callable | None = None,
        task_callback: Callable | None = None,
        event_bridge: CrewAIEventBridge | None = None,
    ) -> Crew:
        has_ssh = ssh_config is not None and ssh_config.get("host")
        target_type, selected = select_agent_names(target, objective, ssh_config)

        logger.debug(
            "Target classification: %s -> type=%s, agents=%s, ssh=%s",
            target, target_type, selected, has_ssh,
        )

        crew_verbose = _env_bool("CREW_VERBOSE", False)
        crew_memory = _env_bool("CREW_MEMORY", False)
        crew_planning = _env_bool("CREW_PLANNING", False)

        core_names = [a for a in selected if a not in SSH_AGENTS]
        agents = self._build_agents(
            core_names, include_ssh=has_ssh, verbose=crew_verbose,
        )

        tasks = self._build_tasks(
            agents=agents,
            target=target,
            scope=scope,
            has_ssh=has_ssh,
            event_bridge=event_bridge,
        )

        if has_ssh:
            self._attach_ssh_tools(agents, ssh_config)
        self._attach_knowledge_tool(agents)
        self._attach_file_io_tools(agents)

        crew_kwargs: dict[str, Any] = {
            "agents": list(agents.values()),
            "tasks": tasks,
            "process": Process.sequential,
            "verbose": crew_verbose,
            "memory": crew_memory,
            "planning": crew_planning,
            "respect_context_window": True,
        }

        if crew_memory and self._embedder_config:
            crew_kwargs["embedder"] = self._embedder_config
        if step_callback:
            crew_kwargs["step_callback"] = step_callback
        if task_callback:
            crew_kwargs["task_callback"] = task_callback

        logger.info(
            "Crew built: %d agents, %d tasks (type=%s, ssh=%s, verbose=%s, memory=%s, planning=%s)",
            len(agents),
            len(tasks),
            target_type,
            has_ssh,
            crew_verbose,
            crew_memory,
            crew_planning,
        )

        return Crew(**crew_kwargs)

    def _build_agents(
        self,
        agent_names: list[str],
        include_ssh: bool = False,
        *,
        verbose: bool = False,
    ) -> dict[str, Agent]:
        common: dict[str, Any] = {
            "llm": self._llm,
            "verbose": verbose,
            "allow_delegation": False,
            "respect_context_window": True,
            "max_iter": 15,
        }

        agents: dict[str, Agent] = {}

        for name in agent_names:
            config = self._agent_prompts.get(name)
            if not config:
                logger.warning("Unknown agent name: %s, skipping", name)
                continue
            tools = to_crewai_tools(self._registry.get_tools_for_agent(name))
            agents[name] = Agent(
                role=config["role"],
                goal=config["goal"],
                backstory=config["backstory"],
                tools=tools,
                **common,
            )
            logger.debug("Built agent: %s (%d tools)", name, len(tools))

        if include_ssh:
            for name in SSH_AGENTS:
                config = self._agent_prompts[name]
                tools = to_crewai_tools(self._registry.get_tools_for_agent(name))
                agents[name] = Agent(
                    role=config["role"],
                    goal=config["goal"],
                    backstory=config["backstory"],
                    tools=tools,
                    **common,
                )
                logger.debug("Built SSH agent: %s (%d tools)", name, len(tools))

        return agents

    def _build_tasks(
        self,
        agents: dict[str, Agent],
        target: str,
        scope: str,
        has_ssh: bool,
        event_bridge: CrewAIEventBridge | None = None,
    ) -> list[Task]:
        scope_str = scope or "only the exact target given"
        fmt = {"target": target, "scope": scope_str}
        td = self._task_templates

        tasks: list[Task] = []

        def _make_task(
            name: str,
            agent_key: str,
            output_pydantic: Any = None,
            context: list[Task] | None = None,
            async_execution: bool = False,
            expected_output: str = "",
        ) -> Task:
            desc = td[name].format(**fmt)
            if not expected_output:
                expected_output = f"Structured {name} results with all security findings in the findings array"
            task = Task(
                description=desc,
                expected_output=expected_output,
                agent=agents[agent_key],
                output_pydantic=output_pydantic,
                context=context or [],
                async_execution=async_execution,
            )
            if event_bridge:
                event_bridge.register_task_agent(desc[:100], agent_key)
            tasks.append(task)
            return task

        # Recon must stay synchronous so other tasks can use `context=[recon_task]` while
        # themselves being async (CrewAI forbids async tasks from referencing prior async
        # tasks in context without a sync task in between).
        recon_task = _make_task(
            "recon", "recon", ReconResult,
            async_execution=False,
            expected_output=(
                "Complete reconnaissance data: subdomains, alive hosts, technology stacks "
                "with exact versions, open ports/services, OSINT data. All discoveries as findings."
            ),
        )

        fuzzer_task = None
        if "fuzzer" in agents:
            fuzzer_task = _make_task(
                "fuzzer", "fuzzer", FuzzerResult,
                async_execution=True,
                expected_output=(
                    "All discovered hidden directories, files, and parameters. "
                    "Each discovery reported as a finding with affected URL and evidence."
                ),
            )

        # After recon, run vuln scanner in parallel with fuzzer (both async; batch completes
        # before the next synchronous task). Placed before crawler so we do not wait for
        # crawler to finish scanning.
        vuln_scan_task = None
        if "vuln_scanner" in agents:
            vuln_scan_task = _make_task(
                "vuln_scanner", "vuln_scanner", VulnScanResult,
                context=[recon_task],
                async_execution=True,
                expected_output=(
                    "All vulnerabilities found by nuclei and nikto, enriched with CVSS scores "
                    "and CISA KEV status from cvedetails. Each as a structured finding."
                ),
            )

        crawler_task = None
        if "crawler" in agents:
            crawler_ctx = [recon_task]
            if fuzzer_task:
                crawler_ctx.append(fuzzer_task)
            crawler_task = _make_task(
                "crawler", "crawler", CrawlerResult,
                context=crawler_ctx,
                expected_output=(
                    "Complete endpoint map: all web pages, JS files, forms, API routes, "
                    "hidden paths, and development artifacts discovered."
                ),
            )

        web_search_task = None
        if "web_search" in agents:
            ws_ctx = [recon_task]
            if vuln_scan_task:
                ws_ctx.append(vuln_scan_task)
            web_search_task = _make_task(
                "web_search", "web_search", WebSearchResult,
                context=ws_ctx,
                expected_output=(
                    "CVEs, public exploits, advisories, and bug bounty reports for all "
                    "technologies found. Each correlated item as a finding."
                ),
            )

        exploit_analysis_task = None
        if "exploit_analyst" in agents:
            analysis_context = [recon_task]
            for t in (fuzzer_task, vuln_scan_task, crawler_task, web_search_task):
                if t:
                    analysis_context.append(t)

            exploit_analysis_task = _make_task(
                "exploit_analyst", "exploit_analyst", ExploitAnalysisResult,
                context=analysis_context,
                expected_output=(
                    "Correlated attack chains, exploitability assessment with CVSS scores, "
                    "false positive identification, and prioritized risk analysis."
                ),
            )

        if has_ssh and "privesc" in agents:
            privesc_ctx = [recon_task]
            if exploit_analysis_task:
                privesc_ctx.append(exploit_analysis_task)
            privesc_task = _make_task(
                "privesc", "privesc", PrivEscResult,
                context=privesc_ctx,
                expected_output=(
                    "Privilege escalation paths: SUID binaries, capabilities, sudo misconfigs, "
                    "writable files, cron jobs, kernel vulns, and harvested credentials."
                ),
            )
            tunnel_task = _make_task(
                "tunnel_pivot", "tunnel_pivot", TunnelPivotResult,
                context=[recon_task, privesc_task],
                expected_output=(
                    "Established tunnels, discovered internal hosts, network segments reached, "
                    "and pivot chain documentation."
                ),
            )
            _make_task(
                "post_exploit", "post_exploit", PostExploitResult,
                context=[privesc_task, tunnel_task],
                expected_output=(
                    "Captured flags, harvested credentials, sensitive files, "
                    "and evidence collected from compromised hosts."
                ),
            )

        if "report_writer" in agents:
            report_context = [t for t in tasks if t is not None]
            report_desc = td["report_writer"].format(**fmt)

            template_content = fetch_report_template()
            if template_content:
                report_desc += (
                    "\n\n## REPORT TEMPLATE REFERENCE\n"
                    "Use this as a structural guide for your report:\n\n"
                    + template_content
                )

            report_task = Task(
                description=report_desc,
                expected_output=(
                    "Structured HuntReport. The complete narrative MUST be in report_markdown as Markdown: "
                    "H1 title; ## sections per task spec; tables; lists; code fences; blockquote callouts; "
                    "every finding from context included. executive_summary is a short blurb only. "
                    "Call knowledge_search (category=reporting) at least once before finalizing. "
                    "Do not return unstructured plain text as the primary deliverable."
                ),
                agent=agents["report_writer"],
                output_pydantic=HuntReport,
                context=report_context,
            )
            if event_bridge:
                event_bridge.register_task_agent(report_desc[:100], "report_writer")
            tasks.append(report_task)

        return tasks

    def _attach_ssh_tools(self, agents: dict[str, Agent], ssh_config: dict[str, Any]) -> None:
        try:
            from app.tools.ssh import (
                SSHCommandTool, SSHFileDownloadTool, SSHFileUploadTool, SSHTunnelTool,
            )
            ssh_tools = [SSHCommandTool(), SSHFileUploadTool(), SSHFileDownloadTool(), SSHTunnelTool()]
            for name in SSH_AGENTS:
                if name in agents:
                    agents[name].tools.extend(ssh_tools)
                    logger.debug("Attached %d SSH tools to %s", len(ssh_tools), name)
        except ImportError as e:
            logger.warning("SSH tools not available: %s", e)

    def _attach_knowledge_tool(self, agents: dict[str, Agent]) -> None:
        try:
            from app.tools.knowledge_query_tool import KnowledgeTool
            knowledge_tool = KnowledgeTool()
            for name in ("exploit_analyst", "privesc", "tunnel_pivot", "post_exploit", "report_writer"):
                if name in agents:
                    agents[name].tools.append(knowledge_tool)
                    logger.debug("Attached knowledge tool to %s", name)
        except ImportError as e:
            logger.warning("Knowledge tool not available: %s", e)

    def _attach_file_io_tools(self, agents: dict[str, Agent]) -> None:
        try:
            from app.tools.file_io import FileReaderTool, FileWriterTool
            file_tools = [FileWriterTool(), FileReaderTool()]
            for name in ("report_writer", "post_exploit"):
                if name in agents:
                    agents[name].tools.extend(file_tools)
                    logger.debug("Attached file I/O tools to %s", name)
        except ImportError as e:
            logger.warning("File I/O tools not available: %s", e)
