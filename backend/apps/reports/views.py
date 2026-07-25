"""Report endpoints — assemble VulnerabilityReport from a run's findings."""
import csv
import io
import json
import re
from collections import Counter

from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.access import run_scope_q, scoped_get_or_404
from apps.findings.models import FindingStatus
from apps.findings.serializers import FindingSerializer
from apps.hunts.budget import default_budget_usd
from apps.hunts.costs import is_priced
from apps.hunts.models import Run

_SEV_TO_SARIF = {"critical": "error", "high": "error", "medium": "warning",
                 "low": "note", "info": "note"}

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]


def _risk_rating(sev_counts: dict) -> str:
    for sev in _SEV_ORDER:
        if sev_counts.get(sev):
            return sev.capitalize()
    return "Informational"


# The only ToolExecution columns the report actually reads. Loading the full
# row would drag `raw_stdout`/`raw_stderr` along — complete nmap/nuclei/ffuf
# output, tens of MB across a `scan_type="full"` run — into the web worker on
# every GET of a report the frontend fetches on mount. Keep this list in sync
# with `_enrich_from_tools` (parsed_result) and `build_report` (tool_name);
# touching any other attribute on these instances triggers a per-row deferred
# -field query, which is worse than the fetch this avoids.
_TOOL_EXEC_REPORT_FIELDS = ("id", "tool_name", "parsed_result")


def _tool_executions_for_report(run: Run) -> list:
    """Fetch the run's tool executions once, with only the columns the report uses."""
    return list(run.tool_executions.only(*_TOOL_EXEC_REPORT_FIELDS))


def _enrich_from_tools(run: Run, tool_executions):
    """Derive discovered services / technologies / endpoints from the persisted
    raw tool outputs (httpx, nmap, whatweb, crawler/fuzzer parsed_result).

    ``tool_executions`` is an already-evaluated sequence (see
    ``_tool_executions_for_report``) so the caller can reuse it instead of
    re-running the query; only ``parsed_result`` is read here.
    """
    services: list[dict] = []
    techs: set[str] = set()
    endpoints = 0
    for te in tool_executions:
        pr = te.parsed_result if isinstance(te.parsed_result, dict) else {}
        for h in pr.get("alive_hosts") or []:
            if isinstance(h, dict):
                techs.update(h.get("tech") or [])
                services.append({
                    "host": h.get("url") or h.get("host") or run.target,
                    "port": h.get("port"),
                    "service": "http",
                    "version": h.get("webserver") or "",
                    "technologies": h.get("tech") or [],
                    "status_code": h.get("status_code"),
                })
        for host in pr.get("hosts") or []:
            if isinstance(host, dict):
                ip = host.get("ip") or host.get("host") or run.target
                for p in host.get("ports") or []:
                    if isinstance(p, dict):
                        services.append({
                            "host": ip, "port": p.get("port"),
                            "service": p.get("service") or p.get("name") or "",
                            "version": p.get("version") or "",
                            "technologies": [], "status_code": None,
                        })
        for p in pr.get("ports") or []:
            if isinstance(p, dict):
                services.append({
                    "host": run.target, "port": p.get("port"),
                    "service": p.get("service") or p.get("name") or "",
                    "version": p.get("version") or "",
                    "technologies": [], "status_code": None,
                })
        techs.update(pr.get("technologies") or [])
        if pr.get("technology"):
            techs.add(pr["technology"])
        for key in ("urls", "paths", "endpoints", "results", "found", "directories"):
            v = pr.get(key)
            if isinstance(v, list):
                endpoints += len(v)
    return services, sorted(t for t in techs if t), endpoints


def cost_payload(
    *,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    cost_usd,
    budget_usd=None,
    model: str = "",
) -> dict:
    """Build the report's ``cost`` block from plain values.

    Deliberately pure (no Django, no DB access): this dict is a contract with
    the frontend ``ReportCost`` interface — the badge renders only when
    ``total_usd`` is present — so it is unit-tested directly.

    ``budget_usd`` of None or 0 means *no ceiling*, and both budget fields then
    come back as ``None`` rather than 0, so the UI can tell "no budget" apart
    from "a budget of zero that is already blown".
    """
    prompt = int(prompt_tokens or 0)
    completion = int(completion_tokens or 0)
    # Older/interrupted runs sometimes have the two halves but no total.
    total = int(total_tokens or 0) or (prompt + completion)
    usd = round(float(cost_usd or 0), 4)
    model = (model or "").strip()

    budget = float(budget_usd or 0)
    budget_out = round(budget, 2) if budget > 0 else None
    used_fraction = round(usd / budget, 4) if budget > 0 else None

    return {
        # Legacy keys — kept so existing consumers (the HTML export footer and
        # any scripted client) keep working; the new keys sit alongside them.
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "usd": usd,
        # Keys the frontend actually reads (see ReportCost in types/api.ts).
        "total_usd": usd,
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": total,
        "model": model,
        # An unpriced (or unknown) model is billed at a fallback rate, so the
        # figure is a guess — label it instead of presenting it as fact.
        "is_estimate": not is_priced(model),
        "budget_usd": budget_out,
        "budget_used_fraction": used_fraction,
    }


def _run_model_name(run: Run) -> str:
    """Best-effort model id for a run — it is not stored on ``Run``.

    Re-resolved the same way ``apps.hunts.tasks`` does. This runs on a read path
    serving an HTTP GET, so it is kept cheap (one indexed vault lookup, no
    network call) and total: any failure degrades to an empty string rather
    than 500-ing the whole report over a cost label.
    """
    try:
        from apps.accounts.keys import keys_provider_for_user
        from redweaver_engine.llm_factory import LLMFactory

        return LLMFactory(keys_provider_for_user(run.created_by)).resolve_model_name() or ""
    except Exception:
        return ""


def build_report(run: Run) -> dict:
    all_findings = list(run.findings.all())
    # Findings triaged or verified as false positives stay in the `findings`
    # array (with their status, so the UI can show what was ruled out) but must
    # not inflate the severity counts, risk rating or remediation plan — a
    # refuted "WordPress RCE" reported as a high would misstate the risk.
    findings = [f for f in all_findings if f.status != FindingStatus.FALSE_POSITIVE]
    false_positives = [f for f in all_findings if f.status == FindingStatus.FALSE_POSITIVE]

    # One query, one materialised list, two consumers (enrichment + tools_used).
    tool_executions = _tool_executions_for_report(run)
    services, technologies, endpoints = _enrich_from_tools(run, tool_executions)
    sev_counts = Counter(f.severity for f in findings)
    agent_counts = Counter(f.agent_source for f in findings if f.agent_source)
    tools_used = sorted(
        {f.tool_used for f in findings if f.tool_used}
        | {te.tool_name for te in tool_executions if te.tool_name}
    )
    agents_executed = sorted({s.agent_name for s in run.agent_steps.all() if s.agent_name})
    return {
        "run_id": str(run.id),
        "target": run.target,
        "executive_summary": (run.report_markdown[:600] if run.report_markdown else ""),
        "scope": run.scope or "",
        "objective": run.objective,
        "methodology": "Automated multi-agent assessment (recon, crawl, scan, fuzz, analysis).",
        "findings": FindingSerializer(all_findings, many=True).data,
        "total_by_severity": dict(sev_counts),
        "findings_by_severity": dict(sev_counts),
        # Counts above exclude these; surfaced separately so a reader can see
        # what the verification pass ruled out rather than it vanishing.
        "false_positive_count": len(false_positives),
        "false_positive_titles": [f.title for f in false_positives],
        "report_markdown": run.report_markdown or "",
        "generated_at": run.completed_at.isoformat() if run.completed_at else run.created_at.isoformat(),
        "risk_rating": _risk_rating(sev_counts),
        "discovered_services": services,
        "discovered_technologies": technologies,
        "total_endpoints": endpoints,
        "findings_by_agent": dict(agent_counts),
        "agents_executed": agents_executed,
        "tools_used": tools_used,
        "remediation_priorities": [
            {
                "finding_id": str(f.id),
                "title": f.title,
                "severity": f.severity,
                "remediation": f.remediation,
                "cvss_score": f.cvss_score,
            }
            for f in sorted(
                findings,
                key=lambda f: _SEV_ORDER.index(f.severity) if f.severity in _SEV_ORDER else 99,
            )[:10]
        ],
        "compliance": _compliance(findings),
        "branding": _branding(run),
        "cost": cost_payload(
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            total_tokens=run.total_tokens,
            cost_usd=run.cost_usd,
            # The *effective* ceiling, matching what BudgetGuard actually
            # enforced: a run with no per-run budget still falls back to the
            # installation-wide RUN_BUDGET_USD, and reporting null there would
            # tell the reader there was no limit when there was.
            budget_usd=run.budget_usd or default_budget_usd(),
            model=_run_model_name(run),
        ),
    }


# OWASP Top 10 (2021) keyword map for compliance reporting.
_OWASP = [
    (("sql injection", "command injection", "xss", "ssrf", "lfi", "rfi", "traversal", "injection"),
     "A03:2021 Injection"),
    (("auth", "default cred", "brute", "password", "session"), "A07:2021 Identification & Auth Failures"),
    (("misconfig", "default", "directory listing", "exposed", "open port", "header"),
     "A05:2021 Security Misconfiguration"),
    (("outdated", "version", "cve-", "vulnerable component", "end of life"),
     "A06:2021 Vulnerable & Outdated Components"),
    (("access", "idor", "authorization", "privilege"), "A01:2021 Broken Access Control"),
    (("crypto", "tls", "ssl", "cleartext", "weak cipher"), "A02:2021 Cryptographic Failures"),
]


def _compliance(findings) -> dict:
    from apps.findings.attack_map import techniques_for

    owasp: dict = {}
    mitre: dict = {}
    for f in findings:
        text = f"{f.title} {f.description}".lower()
        for keys, cat in _OWASP:
            if any(k in text for k in keys):
                owasp[cat] = owasp.get(cat, 0) + 1
                break
        for t in techniques_for(f):
            mitre[f"{t['id']} {t['name']}"] = mitre.get(f"{t['id']} {t['name']}", 0) + 1
    return {
        "owasp_top_10": [{"category": k, "count": v} for k, v in sorted(owasp.items())],
        "mitre_attack": [{"technique": k, "count": v}
                         for k, v in sorted(mitre.items(), key=lambda x: -x[1])],
    }


def _branding(run) -> dict:
    ws = run.workspace if run.workspace_id else None
    return {
        "name": (ws.brand_name if ws and ws.brand_name else "RedWeaver"),
        "color": (ws.brand_color if ws and ws.brand_color else "#3b82f6"),
        "logo_url": (ws.brand_logo_url if ws else "") or "",
    }


# Unified severity palette (matches the frontend theme severityHex).
_SEV_HEX = {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308",
            "low": "#3b82f6", "info": "#64748b"}

_DEFAULT_ACCENT = "#3b82f6"

# `Workspace.brand_color` is free text (CharField, no validators), so it is
# attacker-controlled as far as the renderer is concerned. A CSS hex literal —
# #RGB / #RGBA / #RRGGBB / #RRGGBBAA — is what the field is for; anything else
# is rejected outright.
_CSS_HEX_COLOR_RE = re.compile(r"\A#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\Z")


def safe_accent_color(value, default: str = _DEFAULT_ACCENT) -> str:
    """Return ``value`` if it is a CSS hex colour literal, else ``default``.

    This guards the one interpolation in the HTML export that does *not* land in
    text content but inside a ``<style>`` block (``:root{--accent:...}``), where
    HTML-escaping is the wrong defence: the CSS tokenizer does not decode
    entities, so ``&lt;/style&gt;`` would still be inert while a raw
    ``red}</style><script>...`` payload would break out of the stylesheet and
    run. Allow-listing the shape of a colour is the defence that works.

    Deliberately pure (no Django, no DB) so it is unit-tested directly.
    """
    if not isinstance(value, str):
        return default
    candidate = value.strip()
    return candidate if _CSS_HEX_COLOR_RE.match(candidate) else default


def _render_html(r: dict) -> str:
    """Self-contained premium HTML report rendered from the rich build_report dict
    (the old export path ignored most of this data). Dark theme + print CSS."""
    import html as _h

    def esc(s):
        return _h.escape(str(s or ""))

    brand = r.get("branding") or {}
    # Never interpolated raw: this lands inside <style>, not in text content.
    accent = safe_accent_color(brand.get("color"))
    sev_counts = r.get("findings_by_severity") or {}
    total = sum(sev_counts.values()) or 0

    tiles = "".join(
        f'<div class="tile"><div class="n" style="color:{_SEV_HEX[s]}">{sev_counts.get(s, 0)}</div>'
        f'<div class="l">{s.upper()}</div></div>'
        for s in ["critical", "high", "medium", "low", "info"]
    )
    bar = "".join(
        f'<div style="flex:{max(sev_counts.get(s,0),0)};background:{_SEV_HEX[s]}" title="{s}: {sev_counts.get(s,0)}"></div>'
        for s in ["critical", "high", "medium", "low", "info"] if sev_counts.get(s, 0)
    )
    owasp = "".join(
        f'<span class="chip">{esc(c["category"])} <b>{c["count"]}</b></span>'
        for c in (r.get("compliance", {}).get("owasp_top_10") or [])
    )
    mitre = "".join(
        f'<span class="chip">{esc(m["technique"])} <b>{m["count"]}</b></span>'
        for m in (r.get("compliance", {}).get("mitre_attack") or [])
    )
    rows = ""
    for f in sorted(r.get("findings") or [], key=lambda x: _SEV_ORDER.index(x.get("severity"))
                    if x.get("severity") in _SEV_ORDER else 99):
        sev = (f.get("severity") or "info").lower()
        rows += (
            f'<tr><td><span class="sev" style="background:{_SEV_HEX.get(sev)}1f;color:{_SEV_HEX.get(sev)}">'
            f'{sev.upper()}</span></td><td>{esc(f.get("title"))}</td>'
            f'<td class="mono">{esc(f.get("cvss_score") or "—")}</td>'
            f'<td class="mono">{esc(f.get("risk_score") or "—")} {esc((f.get("risk_decision") or "").upper())}</td>'
            f'<td class="mono">{esc(f.get("affected_url"))}</td></tr>'
        )
    remed = "".join(
        f'<li><b>{esc(p["title"])}</b> <span class="sev" style="background:{_SEV_HEX.get((p.get("severity") or "info").lower())}1f;'
        f'color:{_SEV_HEX.get((p.get("severity") or "info").lower())}">{esc((p.get("severity") or "").upper())}</span>'
        f'<div class="muted">{esc(p.get("remediation"))}</div></li>'
        for p in (r.get("remediation_priorities") or [])
    )
    # light markdown -> html for the narrative
    md = esc(r.get("report_markdown") or "")
    md = re.sub(r"^### (.+)$", r"<h3>\1</h3>", md, flags=re.M)
    md = re.sub(r"^## (.+)$", r"<h2>\1</h2>", md, flags=re.M)
    md = re.sub(r"^# (.+)$", r"<h1>\1</h1>", md, flags=re.M)
    md = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", md)
    md = md.replace("\n", "<br>")
    cost = r.get("cost") or {}

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{esc(brand.get('name','RedWeaver'))} — {esc(r.get('target'))}</title>
<style>
 :root{{--accent:{accent}}}
 *{{box-sizing:border-box}} body{{margin:0;font:14px/1.6 Inter,system-ui,sans-serif;background:#0a0f1e;color:#e6edf3}}
 .wrap{{max-width:980px;margin:0 auto;padding:40px 28px}}
 .hdr{{display:flex;align-items:center;gap:12px;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:16px}}
 .hdr h1{{margin:0;font-size:22px;color:var(--accent)}} .muted{{color:#8b949e}}
 .card{{background:#111827;border:1px solid #1e3a5f;border-radius:12px;padding:22px;margin:20px 0}}
 .verdict{{font-size:48px;font-weight:800;letter-spacing:-1px}}
 .tiles{{display:flex;gap:10px;margin-top:14px}} .tile{{flex:1;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;text-align:center}}
 .tile .n{{font-size:24px;font-weight:700}} .tile .l{{font-size:10px;color:#8b949e;letter-spacing:1px}}
 .bar{{display:flex;height:10px;border-radius:6px;overflow:hidden;margin-top:14px;background:#1e293b}}
 .chip{{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:6px;padding:3px 8px;margin:3px;font-size:12px}}
 table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid rgba(255,255,255,.06)}}
 th{{color:#8b949e;font-size:11px;text-transform:uppercase;letter-spacing:1px}}
 .sev{{padding:2px 8px;border-radius:5px;font-size:11px;font-weight:600}} .mono{{font-family:ui-monospace,monospace;font-size:12px;color:#8b949e}}
 h2{{font-size:14px;text-transform:uppercase;letter-spacing:1px;color:#8b949e;margin:26px 0 10px}}
 .narrative h1,.narrative h2,.narrative h3{{color:#e6edf3;text-transform:none;letter-spacing:0}}
 ol{{padding-left:18px}} li{{margin-bottom:12px}}
 @media print{{body{{background:#fff;color:#111}} .card{{border-color:#ddd;background:#fff;page-break-inside:avoid}} .muted,th{{color:#555}}}}
</style></head><body><div class="wrap">
 <div class="hdr">{('<img src="'+esc(brand['logo_url'])+'" height="36">') if brand.get('logo_url') else ''}
   <div><h1>{esc(brand.get('name','RedWeaver'))}</h1>
   <div class="muted mono">{esc(r.get('target'))} · {esc(r.get('generated_at'))}</div></div></div>
 <div class="card"><div class="muted">OVERALL RISK RATING</div>
   <div class="verdict" style="color:{_SEV_HEX.get((r.get('risk_rating') or 'info').lower(), accent)}">{esc(r.get('risk_rating'))}</div>
   <div class="muted">{total} findings · {esc(r.get('target'))}</div>
   <div class="tiles">{tiles}</div><div class="bar">{bar}</div></div>
 {('<div class="card"><h2 style="margin-top:0">Executive Summary</h2><div class="narrative">'+md+'</div></div>') if md else ''}
 <div class="card"><h2 style="margin-top:0">Compliance — OWASP Top 10</h2>{owasp or '<span class="muted">—</span>'}
   <h2>MITRE ATT&CK</h2>{mitre or '<span class="muted">—</span>'}</div>
 <div class="card"><h2 style="margin-top:0">Findings ({total})</h2>
   <table><tr><th>Severity</th><th>Title</th><th>CVSS</th><th>Risk</th><th>Affected</th></tr>{rows}</table></div>
 {('<div class="card"><h2 style="margin-top:0">Remediation Priorities</h2><ol>'+remed+'</ol></div>') if remed else ''}
 <div class="muted" style="text-align:center;margin-top:24px;font-size:12px">
   Generated by {esc(brand.get('name','RedWeaver'))} · {cost.get('total_tokens',0)} tokens · ${cost.get('usd',0)}</div>
</div></body></html>"""


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_report(request, run_id):
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    return Response(build_report(run))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def run_report_export(request, run_id):
    """Export a run's report as ?fmt=json|csv|sarif (SARIF unlocks CI/CD).

    Note: the param is ``fmt`` (not ``format``) because DRF reserves ``format``
    for content negotiation and 404s on unknown renderer names.
    """
    run = scoped_get_or_404(Run, request.user, run_scope_q, id=run_id)
    fmt = (request.query_params.get("fmt") or "json").lower()
    findings = FindingSerializer(
        run.findings.all().order_by("severity"), many=True
    ).data
    base = f"redweaver-{str(run.id)[:8]}"

    if fmt == "json":
        resp = HttpResponse(
            json.dumps(build_report(run), indent=2, default=str),
            content_type="application/json",
        )
        resp["Content-Disposition"] = f'attachment; filename="{base}.json"'
        return resp

    if fmt == "html":
        try:
            html = _render_html(build_report(run))
        except Exception as exc:  # noqa: BLE001
            return Response({"error": f"html render failed: {exc}"}, status=500)
        resp = HttpResponse(html, content_type="text/html")
        resp["Content-Disposition"] = f'attachment; filename="{base}.html"'
        return resp

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["severity", "title", "affected_url", "cvss_score", "cve_ids",
                    "status", "confidence", "description", "remediation"])
        for f in findings:
            w.writerow([
                f.get("severity"), f.get("title"), f.get("affected_url"),
                f.get("cvss_score"), ",".join(f.get("cve_ids") or []),
                f.get("status"), f.get("confidence"),
                (f.get("description") or "").replace("\n", " "),
                (f.get("remediation") or "").replace("\n", " "),
            ])
        resp = HttpResponse(buf.getvalue(), content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{base}.csv"'
        return resp

    if fmt == "sarif":
        results = []
        for f in findings:
            loc = f.get("affected_url") or run.target
            results.append({
                "ruleId": (f.get("cve_ids") or [f.get("title")])[0] or "finding",
                "level": _SEV_TO_SARIF.get((f.get("severity") or "info").lower(), "note"),
                "message": {"text": f.get("title") or "Finding"},
                "locations": (
                    [{"physicalLocation": {"artifactLocation": {"uri": loc}}}] if loc else []
                ),
                "properties": {
                    "cvss": f.get("cvss_score"),
                    "confidence": f.get("confidence"),
                    "agent": f.get("agent_source"),
                    "severity": f.get("severity"),
                },
            })
        sarif = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {"driver": {
                    "name": "RedWeaver",
                    "informationUri": "https://github.com/TarzEH/RedWeaver",
                    "rules": [],
                }},
                "results": results,
            }],
        }
        resp = HttpResponse(json.dumps(sarif, indent=2), content_type="application/sarif+json")
        resp["Content-Disposition"] = f'attachment; filename="{base}.sarif"'
        return resp

    return Response({"error": f"unsupported format: {fmt}"}, status=400)
