"""Map findings to MITRE ATT&CK techniques and build a Navigator layer.

A heuristic keyword map turns each finding into one or more ATT&CK techniques
(grounded in the actual finding, not LLM-asserted), and ``navigator_layer``
emits a valid ATT&CK Navigator JSON layer that opens directly in
https://mitre-attack.github.io/attack-navigator/ — a real engagement artifact
showing the attack path across the kill chain.
"""
from __future__ import annotations

# keyword(s) -> list of (technique_id, name, tactic)
_RULES: list[tuple[tuple[str, ...], list[tuple[str, str, str]]]] = [
    (("sql injection", "sqli"), [("T1190", "Exploit Public-Facing Application", "initial-access")]),
    (("cross-site scripting", "xss"), [("T1059.007", "JavaScript", "execution"),
                                       ("T1190", "Exploit Public-Facing Application", "initial-access")]),
    (("command injection", "rce", "remote code execution", "code execution"),
     [("T1190", "Exploit Public-Facing Application", "initial-access"),
      ("T1059", "Command and Scripting Interpreter", "execution")]),
    (("traversal", "lfi", "local file inclusion", "path"),
     [("T1083", "File and Directory Discovery", "discovery"),
      ("T1190", "Exploit Public-Facing Application", "initial-access")]),
    (("upload", "web shell", "webshell"), [("T1505.003", "Web Shell", "persistence")]),
    (("ssh", "ftp", "rdp", "brute", "password", "credential"),
     [("T1110", "Brute Force", "credential-access")]),
    (("privilege escalation", "suid", "sudo", "privesc"),
     [("T1068", "Exploitation for Privilege Escalation", "privilege-escalation")]),
    (("harvest", "credential dump", "hashes"),
     [("T1003", "OS Credential Dumping", "credential-access")]),
    (("open port", "open tcp", "service", "port ", "sip", "rtp", "smb", "netbios"),
     [("T1046", "Network Service Discovery", "discovery")]),
    (("subdomain", "dns", "whois", "osint", "harvester"),
     [("T1595", "Active Scanning", "reconnaissance")]),
    (("exfil", "data leak", "sensitive data"), [("T1041", "Exfiltration Over C2 Channel", "exfiltration")]),
    (("cve-", "vulnerab", "outdated", "version"),
     [("T1203", "Exploitation for Client Execution", "execution")]),
]
_FALLBACK = [("T1190", "Exploit Public-Facing Application", "initial-access")]

# severity -> heat color for the Navigator layer
_HEAT = {"critical": "#e11d48", "high": "#f97316", "medium": "#eab308",
         "low": "#3b82f6", "info": "#64748b"}


def techniques_for(finding) -> list[dict]:
    get = (lambda k: getattr(finding, k, None)) if not isinstance(finding, dict) else finding.get
    text = f"{get('title') or ''} {get('description') or ''}".lower()
    out: list[dict] = []
    seen: set[str] = set()
    for keys, techs in _RULES:
        if any(k in text for k in keys):
            for tid, name, tactic in techs:
                if tid not in seen:
                    seen.add(tid)
                    out.append({"id": tid, "name": name, "tactic": tactic})
    if not out:
        for tid, name, tactic in _FALLBACK:
            out.append({"id": tid, "name": name, "tactic": tactic})
    return out


def navigator_layer(run, findings) -> dict:
    """Build an ATT&CK Navigator (v4.5) layer from a run's findings."""
    sev_rank = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
    agg: dict[str, dict] = {}
    for f in findings:
        get = (lambda k: getattr(f, k, None)) if not isinstance(f, dict) else f.get
        sev = (get("severity") or "info").lower()
        for t in techniques_for(f):
            cur = agg.setdefault(t["id"], {"score": 0, "sev": "info", "name": t["name"], "comments": []})
            cur["score"] += 1
            if sev_rank.get(sev, 0) > sev_rank.get(cur["sev"], 0):
                cur["sev"] = sev
            title = get("title")
            if title and title not in cur["comments"]:
                cur["comments"].append(title)

    techniques = [{
        "techniqueID": tid,
        "score": d["score"],
        "color": _HEAT.get(d["sev"], "#64748b"),
        "comment": "; ".join(d["comments"][:6]),
        "enabled": True,
    } for tid, d in agg.items()]

    target = getattr(run, "target", "") or ""
    return {
        "name": f"RedWeaver — {target}"[:120],
        "versions": {"attack": "15", "navigator": "4.9.1", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": f"Attack techniques observed by RedWeaver against {target}.",
        "sorting": 3,
        "hideDisabled": True,
        "techniques": techniques,
        "gradient": {"colors": ["#1e3a5f", "#e11d48"], "minValue": 0,
                     "maxValue": max([t["score"] for t in techniques] + [1])},
        "legendItems": [],
        "showTacticRowBackground": True,
        "tacticRowBackground": "#0a0f1e",
    }
