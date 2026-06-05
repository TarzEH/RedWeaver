"""Pre-hunt ATT&CK planning.

Turns a set of MITRE ATT&CK techniques (typically selected by the user in the
ATT&CK Navigator, https://mitre-attack.github.io/attack-navigator/, and exported
as a layer JSON) into a concrete hunt plan: which RedWeaver agents to run and a
focus directive injected into every task so the crew prioritizes those
techniques.

Framework-agnostic (no Django imports) so it can be unit-tested and reused by the
crew builder and the API preview endpoint alike.
"""

from __future__ import annotations

from typing import Any

# ATT&CK tactic (Navigator "tactic" / shortname) -> RedWeaver agents that can
# exercise that tactic. Keep keys in ATT&CK shortname form (hyphenated).
TACTIC_AGENTS: dict[str, list[str]] = {
    "reconnaissance": ["recon", "web_search"],
    "resource-development": ["web_search"],
    "initial-access": ["recon", "crawler", "vuln_scanner", "fuzzer", "exploit_analyst"],
    "execution": ["vuln_scanner", "exploit_analyst"],
    "persistence": ["exploit_analyst", "post_exploit"],
    "privilege-escalation": ["privesc", "exploit_analyst"],
    "defense-evasion": ["exploit_analyst", "post_exploit"],
    "credential-access": ["vuln_scanner", "web_search", "post_exploit"],
    "discovery": ["recon", "crawler", "fuzzer", "vuln_scanner"],
    "lateral-movement": ["tunnel_pivot", "post_exploit"],
    "collection": ["post_exploit"],
    "command-and-control": ["exploit_analyst", "tunnel_pivot"],
    "exfiltration": ["post_exploit"],
    "impact": ["exploit_analyst"],
}

# Known technique id -> (tactic, display name). Covers the techniques RedWeaver
# emits in attack_map plus common Navigator picks. Sub-technique ids fall back to
# their parent (e.g. T1059.007 -> T1059) when the exact id is unknown.
TECHNIQUE_INFO: dict[str, tuple[str, str]] = {
    "T1595": ("reconnaissance", "Active Scanning"),
    "T1592": ("reconnaissance", "Gather Victim Host Information"),
    "T1590": ("reconnaissance", "Gather Victim Network Information"),
    "T1589": ("reconnaissance", "Gather Victim Identity Information"),
    "T1596": ("reconnaissance", "Search Open Technical Databases"),
    "T1190": ("initial-access", "Exploit Public-Facing Application"),
    "T1133": ("initial-access", "External Remote Services"),
    "T1078": ("initial-access", "Valid Accounts"),
    "T1059": ("execution", "Command and Scripting Interpreter"),
    "T1203": ("execution", "Exploitation for Client Execution"),
    "T1505": ("persistence", "Server Software Component"),
    "T1098": ("persistence", "Account Manipulation"),
    "T1068": ("privilege-escalation", "Exploitation for Privilege Escalation"),
    "T1548": ("privilege-escalation", "Abuse Elevation Control Mechanism"),
    "T1134": ("privilege-escalation", "Access Token Manipulation"),
    "T1562": ("defense-evasion", "Impair Defenses"),
    "T1027": ("defense-evasion", "Obfuscated Files or Information"),
    "T1055": ("defense-evasion", "Process Injection"),
    "T1110": ("credential-access", "Brute Force"),
    "T1003": ("credential-access", "OS Credential Dumping"),
    "T1212": ("credential-access", "Exploitation for Credential Access"),
    "T1552": ("credential-access", "Unsecured Credentials"),
    "T1558": ("credential-access", "Steal or Forge Kerberos Tickets"),
    "T1046": ("discovery", "Network Service Discovery"),
    "T1083": ("discovery", "File and Directory Discovery"),
    "T1087": ("discovery", "Account Discovery"),
    "T1018": ("discovery", "Remote System Discovery"),
    "T1069": ("discovery", "Permission Groups Discovery"),
    "T1482": ("discovery", "Domain Trust Discovery"),
    "T1021": ("lateral-movement", "Remote Services"),
    "T1210": ("lateral-movement", "Exploitation of Remote Services"),
    "T1090": ("command-and-control", "Proxy"),
    "T1071": ("command-and-control", "Application Layer Protocol"),
    "T1572": ("command-and-control", "Protocol Tunneling"),
    "T1573": ("command-and-control", "Encrypted Channel"),
    "T1041": ("exfiltration", "Exfiltration Over C2 Channel"),
    "T1567": ("exfiltration", "Exfiltration Over Web Service"),
}

# Agents that always run regardless of focus: recon establishes the surface every
# other agent depends on; report_writer produces the deliverable.
_ALWAYS = ["recon", "report_writer"]

# Canonical crew construction order (non-SSH first, then SSH).
_ORDER = [
    "recon", "crawler", "vuln_scanner", "fuzzer", "web_search",
    "exploit_analyst", "report_writer", "privesc", "tunnel_pivot", "post_exploit",
]
_SSH_AGENTS = {"privesc", "tunnel_pivot", "post_exploit"}


def normalize_technique_id(tid: str) -> str:
    """Uppercase + trim a technique id, e.g. ' t1190 ' -> 'T1190'."""
    return (tid or "").strip().upper()


def technique_tactic(tid: str) -> str | None:
    """Resolve a technique id (or sub-technique) to its tactic, or None."""
    tid = normalize_technique_id(tid)
    if not tid:
        return None
    if tid in TECHNIQUE_INFO:
        return TECHNIQUE_INFO[tid][0]
    parent = tid.split(".", 1)[0]
    if parent in TECHNIQUE_INFO:
        return TECHNIQUE_INFO[parent][0]
    return None


def parse_navigator_layer(layer: Any) -> list[str]:
    """Extract selected technique ids from an ATT&CK Navigator layer JSON.

    A technique counts as selected when it is not explicitly disabled and carries
    a signal of intent (a score, a non-default color, a comment, or being marked
    enabled). Accepts the raw layer dict (or a JSON string already parsed).
    """
    if not isinstance(layer, dict):
        return []
    techniques = layer.get("techniques") or []
    selected: list[str] = []
    seen: set[str] = set()
    for t in techniques:
        if not isinstance(t, dict):
            continue
        tid = normalize_technique_id(t.get("techniqueID") or t.get("techniqueId") or "")
        if not tid or tid in seen:
            continue
        if t.get("enabled") is False:
            continue
        has_signal = (
            t.get("score") not in (None, 0)
            or bool(t.get("color"))
            or bool(t.get("comment"))
            or t.get("enabled") is True
        )
        if has_signal:
            seen.add(tid)
            selected.append(tid)
    return selected


def plan_from_techniques(
    technique_ids: list[str],
    target_agents: list[str],
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a hunt plan from selected ATT&CK techniques.

    Args:
        technique_ids: selected ATT&CK technique ids (sub-techniques allowed).
        target_agents: the agent set the target type would normally use — the
            focus selection is intersected with this so we never invent agents
            that do not apply to the target (e.g. SSH agents without SSH).
        ssh_config: when present with a host, SSH-tier agents are eligible.

    Returns dict: {techniques, unknown, tactics, agent_selection, focus}.
    """
    has_ssh = bool(ssh_config and ssh_config.get("host"))
    eligible = set(target_agents)
    if has_ssh:
        eligible |= _SSH_AGENTS

    techs: list[str] = []
    unknown: list[str] = []
    tactics: list[str] = []
    agents: set[str] = set()

    for raw in technique_ids:
        tid = normalize_technique_id(raw)
        if not tid:
            continue
        if tid not in techs:
            techs.append(tid)
        tactic = technique_tactic(tid)
        if tactic is None:
            unknown.append(tid)
            continue
        if tactic not in tactics:
            tactics.append(tactic)
        for a in TACTIC_AGENTS.get(tactic, []):
            if a in eligible:
                agents.add(a)

    # Always include the baseline agents (that apply to this target).
    for a in _ALWAYS:
        if a in eligible:
            agents.add(a)

    # If nothing resolved (e.g. only unknown techniques), fall back to the full
    # target agent set so the hunt still runs rather than silently degrading.
    if not agents - set(_ALWAYS):
        agents |= eligible

    agent_selection = [a for a in _ORDER if a in agents]
    focus = build_focus(techs, tactics)
    return {
        "techniques": techs,
        "unknown": unknown,
        "tactics": tactics,
        "agent_selection": agent_selection,
        "focus": focus,
    }


def build_focus(technique_ids: list[str], tactics: list[str]) -> str:
    """Build the ATT&CK FOCUS directive appended to each task description."""
    if not technique_ids:
        return ""
    lines = []
    for tid in technique_ids:
        info = TECHNIQUE_INFO.get(tid) or TECHNIQUE_INFO.get(tid.split(".", 1)[0])
        name = info[1] if info else "(unmapped)"
        lines.append(f"  - {tid} {name}")
    tactic_str = ", ".join(tactics) if tactics else "n/a"
    return (
        "## ATT&CK FOCUS (pre-hunt plan)\n"
        "This engagement is SCOPED to the following MITRE ATT&CK techniques chosen "
        "by the operator. Prioritize testing for these and report coverage for each; "
        "tactics in scope: " + tactic_str + ".\n"
        + "\n".join(lines)
    )
