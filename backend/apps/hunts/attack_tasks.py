"""Celery task: generate an on-demand Attack playbook from a run's findings."""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.accounts.keys import keys_provider_for_user
from apps.observability.publisher import publish

from .crew_factory import _build_crewai_llm
from .models import Run

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_attack_playbook(self, run_id: str) -> None:
    run = Run.objects.filter(id=run_id).select_related("created_by").first()
    if not run:
        return

    run.attack_status = "running"
    run.save(update_fields=["attack_status", "updated_at"])
    publish(str(run.id), "attack_start", {"agent": "attack"})

    from redweaver_engine.crews.attack import build_attack_crew
    from redweaver_engine.llm_factory import LLMFactory
    from redweaver_engine.tools.instrumentation import run_context
    from redweaver_engine.tools.registry import ToolRegistry

    from apps.findings.serializers import FindingSerializer

    kp = keys_provider_for_user(run.created_by)
    lf = LLMFactory(kp)
    if not lf.has_api_key():
        run.attack_status = "failed"
        run.save(update_fields=["attack_status", "updated_at"])
        publish(str(run.id), "attack_error", {"error": "No LLM API key configured"})
        return

    keys = kp.get_all()
    llm = _build_crewai_llm(lf, keys)
    registry = ToolRegistry(
        virustotal_api_key=keys.get("virustotal_api_key"),
        urlscan_api_key=keys.get("urlscan_api_key"),
    )
    findings = FindingSerializer(run.findings.all(), many=True).data

    with run_context(str(run.id), "attack"):
        try:
            publish(str(run.id), "attack_research",
                    {"agent": "attack", "msg": "researching knowledge base + web + CVEs"})
            research_md = gather_research(registry, run.target or "", findings)
            crew = build_attack_crew(
                llm=llm,
                registry=registry,
                target=run.target or "",
                findings=findings,
                run_id=str(run.id),
                research_context=research_md,
            )
            result = crew.kickoff()
            md = (getattr(result, "raw", None) or str(result) or "").strip()
            run.attack_markdown = md
            run.attack_status = "completed"
            run.save(update_fields=["attack_markdown", "attack_status", "updated_at"])
            publish(str(run.id), "attack_complete", {"agent": "attack", "length": len(md)})
        except Exception as exc:  # noqa: BLE001
            logger.exception("attack playbook failed for %s", run_id)
            run.attack_status = "failed"
            run.save(update_fields=["attack_status", "updated_at"])
            publish(str(run.id), "attack_error", {"error": str(exc)})


import os as _os
import httpx as _httpx
from concurrent.futures import ThreadPoolExecutor as _Pool

_KB_URL = _os.environ.get("KNOWLEDGE_SERVICE_URL", "http://knowledge:8100").rstrip("/")

# Map a finding to the most relevant KB methodology queries (so we pull the
# right attack technique + commands, not generic chunks).
_KB_MAP = [
    (("ssh",), ["SSH password attack hydra brute force"]),
    (("ftp",), ["FTP password attack hydra"]),
    (("rdp",), ["RDP password attack hydra"]),
    (("smb", "netbios"), ["SMB enumeration attack", "service enumeration SMB"]),
    (("sql",), ["sql injection sqlmap exploitation"]),
    (("xss",), ["cross site scripting payload"]),
    (("lfi", "inclusion", "traversal", "path"), ["directory traversal path traversal", "local file inclusion exploitation"]),
    (("upload",), ["file upload attack web shell"]),
    (("apache", "http", "nginx", "web", "cgi", "userdir"),
     ["web application attacks", "directory traversal path traversal", "command injection web"]),
    (("sip", "voip", "sccp", "rtp"), ["service enumeration network services"]),
    (("port", "service", "open tcp"), ["service enumeration", "port scanning enumeration"]),
]


def _kb_terms_for(finding: dict) -> list:
    t = (finding.get("title") or "").lower()
    terms: list = []
    for keys, qs in _KB_MAP:
        if any(k in t for k in keys):
            terms += qs
    if finding.get("cve_ids"):
        terms.append("finding and using public exploits metasploit")
    if not terms:
        terms.append(f"{t} exploitation")
    # dedup, keep order, cap 2 per finding
    return list(dict.fromkeys(terms))[:2]


def _kb_query(q: str, top_k: int = 3) -> list:
    # Fast/accurate retrieval straight from the Postgres pgvector RAG (no HTTP).
    try:
        from apps.knowledge.search import kb_search
        return kb_search(q, top_k=top_k, min_score=0.18)
    except Exception:
        return []


def gather_research(registry, target: str, findings: list) -> str:
    """DEEP per-finding research IN PARALLEL: for each finding map to the right
    KB attack methodology (commands), pull CVE details + a public PoC, and build
    a per-finding dossier the agent grounds its attack plan on. Plus shared
    privesc/post-ex methodology from the KB."""
    web = registry.get_tool("web_search")
    cve_tool = registry.get_tool("cvedetails_lookup")

    def web_q(q):
        try:
            res = web.run(q) if web else {}
            return res.get("results", []) if isinstance(res, dict) else []
        except Exception:
            return []

    def cve_q(c):
        try:
            return cve_tool.run(c) if cve_tool else {}
        except Exception:
            return {}

    def research_one(f: dict):
        kb_hits = []
        for q in _kb_terms_for(f):
            for r in _kb_query(q, top_k=2)[:2]:
                kb_hits.append((r.get("file", "kb"), (r.get("content") or "")[:1300]))
        cves = (f.get("cve_ids") or [])[:2]
        cve_info = {c: cve_q(c) for c in cves}
        web_hits = []
        for c in cves:
            web_hits += web_q(f"{c} exploit proof of concept github")[:2]
        if not cves:
            web_hits += web_q(f"{f.get('title', '')} {target} exploit")[:1]
        return (f, kb_hits, cve_info, web_hits)

    # rank findings by severity so the most important get researched first/most
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    ranked = sorted(findings, key=lambda f: order.get((f.get("severity") or "info").lower(), 5))[:8]

    with _Pool(max_workers=8) as ex:
        results = list(ex.map(research_one, ranked))
    # shared methodology (run in parallel too)
    with _Pool(max_workers=4) as ex:
        gen = list(ex.map(lambda q: (q, _kb_query(q, top_k=2)),
                          ["linux privilege escalation methodology",
                           "post exploitation credential harvesting"]))

    # ---- ENGAGEMENT INTEL: computed real-data prioritization (SSVC + EPSS + KEV
    # + exploit availability + MITRE ATT&CK) so the report prioritizes by real
    # risk, not CVSS alone (~2% of CVEs are exploited in the wild). ----
    try:
        from apps.findings.risk import risk_for_finding
        from apps.findings.attack_map import techniques_for

        scored = []
        for f in findings:
            r = risk_for_finding(f)
            scored.append((r["risk_score"], r["decision"], r["weaponized"], f, techniques_for(f)))
        scored.sort(key=lambda x: x[0], reverse=True)
        dcount: dict = {}
        for s in scored:
            dcount[s[1]] = dcount.get(s[1], 0) + 1
        intel = [
            "## ENGAGEMENT INTEL (computed — PRIORITIZE BY THIS, not CVSS alone)",
            f"Findings: {len(findings)} · SSVC decisions: "
            + ", ".join(f"{k}={v}" for k, v in dcount.items()),
            "| Finding | Sev | Risk | SSVC | EPSS | KEV | Exploit | ATT&CK |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for score, dec, weap, f, techs in scored[:15]:
            epss = f.get("epss_score")
            epss_s = f"{epss * 100:.1f}%" if isinstance(epss, (int, float)) else "—"
            tt = ", ".join(t["id"] for t in techs[:2])
            intel.append(
                f"| {(f.get('title') or '')[:48]} | {(f.get('severity') or 'info')} | "
                f"{score} | {dec} | {epss_s} | {'yes' if f.get('cisa_kev') else 'no'} | "
                f"{'weaponized' if weap else 'none'} | {tt} |"
            )
        blocks: list = intel + ["", "## Shared methodology (from KB)"]
    except Exception:
        blocks = ["## Shared methodology (from KB)"]
    seen = set()
    for _q, hits in gen:
        for r in hits[:1]:
            key = r.get("file")
            if key in seen:
                continue
            seen.add(key)
            blocks.append(f"- _{r.get('file')}_:\n{(r.get('content') or '')[:900]}")

    blocks.append("\n## Per-finding research dossier")
    for f, kb_hits, cve_info, web_hits in results:
        sev = (f.get("severity") or "info").upper()
        blocks.append(
            f"\n### [{sev}] {f.get('title', '')}  (affected: {f.get('affected_url') or target})"
        )
        for file, content in kb_hits:
            k = (file, content[:50])
            if k in seen:
                continue
            seen.add(k)
            blocks.append(f"- **KB technique** _{file}_:\n{content}")
        for c, info in cve_info.items():
            if info:
                blocks.append(f"- **CVE {c}**: {str(info)[:400]}")
        for w in web_hits[:2]:
            if isinstance(w, dict):
                snip = (w.get("snippet") or w.get("body") or w.get("description") or "")[:180]
                blocks.append(f"- **Public** [{w.get('title', 'exploit')}]({w.get('url', '')}): {snip}")

    out = "\n".join(blocks)
    return out[:18000] if out.strip() else "(no external research results returned)"
