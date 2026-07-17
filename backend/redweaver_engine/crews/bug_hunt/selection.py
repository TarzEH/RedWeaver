"""Target classification and agent set selection (shared by crew builder and graph API)."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

# Agent sets per target type (core pipeline, before SSH)
TARGET_AGENT_MAP: dict[str, list[str]] = {
    "web": [
        "recon", "crawler", "vuln_scanner", "fuzzer",
        "web_search", "exploit_analyst", "report_writer",
    ],
    "network": [
        "recon", "vuln_scanner", "fuzzer",
        "exploit_analyst", "report_writer",
    ],
    "host": [
        "recon", "vuln_scanner", "fuzzer",
        "exploit_analyst", "report_writer",
    ],
}

SSH_AGENTS = ["privesc", "tunnel_pivot", "post_exploit"]


def classify_target(target: str) -> str:
    """Classify target as 'web', 'network', or 'host'."""
    no_proto = re.sub(r"^https?://", "", target).strip()

    if "/" in no_proto:
        cidr_part = no_proto.split(":")[0]
        try:
            ipaddress.ip_network(cidr_part, strict=False)
            return "network"
        except ValueError:
            pass

    stripped = no_proto.split("/")[0].split(":")[0]

    try:
        ipaddress.ip_address(stripped)
        return "host"
    except ValueError:
        pass

    return "web"


def select_agent_names(
    target: str,
    objective: str = "comprehensive",
    ssh_config: dict[str, Any] | None = None,
    attack_techniques: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Return (target_type, flat list of agent keys used for this hunt, in crew construction order).

    When ``attack_techniques`` (a list of MITRE ATT&CK technique ids, typically
    chosen by the operator in the ATT&CK Navigator) is provided, the agent set is
    scoped to the agents that exercise the tactics behind those techniques —
    intersected with the agents valid for the target type — instead of the full
    objective-based set.
    """
    is_quick = objective.lower() in ("quick", "fast", "minimal")
    has_ssh = ssh_config is not None and bool(ssh_config.get("host"))

    target_type = classify_target(target)
    selected = list(TARGET_AGENT_MAP.get(target_type, TARGET_AGENT_MAP["web"]))

    if is_quick:
        selected = [a for a in selected if a not in ("crawler", "web_search")]

    if attack_techniques:
        # ATT&CK-scoped plan: derive agents from the selected techniques, bounded
        # by the agents valid for this target (+ SSH tier when configured).
        from redweaver_engine.crews.bug_hunt.attack_planning import plan_from_techniques

        plan = plan_from_techniques(attack_techniques, selected, ssh_config)
        return target_type, plan["agent_selection"]

    if has_ssh:
        selected = [*selected, *SSH_AGENTS]

    return target_type, selected
