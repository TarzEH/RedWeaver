import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { ShieldAlert, ListChecks, DollarSign, ExternalLink } from "lucide-react";
import { api } from "../../services/api";
import type { AttackChain } from "../../services/api";
import { ApiError } from "../../services/http";
import { useToast } from "../../components/ui/feedback";
import { openInNavigator } from "../../lib/navigator";
import type { Finding, VulnerabilityReport } from "../../types/api";
import { severityHex, SEVERITY_ORDER } from "../../config/theme";
import { Spinner } from "../../components/ui/Spinner";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { MarkdownRenderer } from "../../components/domain/MarkdownRenderer";
import { VerdictHero } from "../../components/domain/report/VerdictHero";
import { SeverityBar } from "../../components/domain/report/SeverityBar";
import { CvssEpssScatter } from "../../components/domain/report/CvssEpssScatter";
import { MitreHeatmap } from "../../components/domain/report/MitreHeatmap";
import { AttackPathGraph } from "../../components/domain/report/AttackPathGraph";
import { AttackGraphView } from "../../components/domain/AttackGraphView";
import { buildReportMarkdown } from "./buildReportMarkdown";
import { cn } from "../../lib/cn";

interface ReportViewProps {
  /** Run id. Falls back to the `:runId` route param when omitted. */
  runId?: string;
}

/** Derive an ordinal severity → count map from structured maps or raw findings. */
function severityCounts(report: VulnerabilityReport): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const s of SEVERITY_ORDER) counts[s] = 0;
  const src = report.total_by_severity ?? report.findings_by_severity;
  if (src) {
    for (const [k, v] of Object.entries(src)) {
      const key = k.toLowerCase();
      if (key in counts) counts[key] += Number(v) || 0;
    }
    return counts;
  }
  for (const f of report.findings ?? ([] as Finding[])) {
    const key = (f.severity || "info").toLowerCase();
    if (key in counts) counts[key] += 1;
  }
  return counts;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-rw-muted">{children}</h2>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-rw-elevated px-3 py-2">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-rw-dim">{label}</div>
      <div className="mt-0.5 break-words text-sm text-rw-text">{value}</div>
    </div>
  );
}

export function ReportView({ runId: runIdProp }: ReportViewProps) {
  const params = useParams<{ runId?: string }>();
  const runId = runIdProp ?? params.runId;

  const [report, setReport] = useState<VulnerabilityReport | null>(null);
  const [chains, setChains] = useState<AttackChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  const openCoverageInNavigator = async () => {
    if (!runId) return;
    try {
      const layer = await api.runs.attackNavigator(runId);
      openInNavigator(layer, `redweaver-${runId.slice(0, 8)}-coverage.json`);
      toast.info("Coverage layer downloaded — in the Navigator choose 'Open Existing Layer → Upload'.");
    } catch {
      toast.error("Could not build the ATT&CK Navigator layer for this run.");
    }
  };

  useEffect(() => {
    if (!runId) {
      setReport(null);
      setError("No run selected.");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setReport(null);
    setChains([]);

    Promise.all([
      api.runs.report(runId),
      api.runs.attackChains(runId).catch(() => [] as AttackChain[]),
    ])
      .then(([r, c]) => {
        if (cancelled) return;
        setReport(r);
        setChains(Array.isArray(c) ? c : []);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(
          e instanceof ApiError
            ? `${e.status}: ${e.message}`
            : e instanceof Error
              ? e.message
              : "Failed to load report",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId]);

  const counts = useMemo(() => (report ? severityCounts(report) : {}), [report]);
  const markdown = useMemo(() => (report ? buildReportMarkdown(report) : ""), [report]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center bg-rw-bg py-24">
        <Spinner size="lg" label="Loading report…" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex flex-1 items-center justify-center bg-rw-bg p-6">
        <div className="rounded-xl border border-rw-border bg-rw-elevated px-6 py-5 text-sm text-rw-dim">
          {error ?? "Report unavailable."}
        </div>
      </div>
    );
  }

  const brand = report.branding;
  const brandColor = brand?.color || "var(--color-rw-accent)";
  const owasp = report.compliance?.owasp_top_10 ?? [];
  const mitre = report.compliance?.mitre_attack ?? [];
  const priorities = report.remediation_priorities ?? [];
  const cost = report.cost;

  return (
    <div className="flex-1 overflow-y-auto bg-rw-bg p-6 animate-fade-in">
      <div className="mx-auto max-w-6xl space-y-8">
        {/* Branded header */}
        <header className="flex flex-wrap items-center gap-4 border-b border-rw-border pb-5">
          {brand?.logo_url ? (
            <img
              src={brand.logo_url}
              alt={brand?.name ? `${brand.name} logo` : "Report logo"}
              className="h-10 w-10 rounded-lg object-contain"
            />
          ) : (
            <span
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/10"
              style={{ background: `${brandColor}22` }}
            >
              <ShieldAlert size={20} style={{ color: brandColor }} />
            </span>
          )}
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold tracking-tight" style={{ color: brandColor }}>
              {brand?.name || "Security Assessment Report"}
            </h1>
            <p className="font-mono text-xs text-rw-dim">
              {report.target} · {new Date(report.generated_at).toLocaleString()}
            </p>
          </div>
          {cost?.total_usd != null && (
            <span className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-rw-border bg-rw-surface/50 px-2.5 py-1 text-xs text-rw-muted">
              <DollarSign size={13} className="text-rw-dim" />
              <span className="tabular-nums">${cost.total_usd.toFixed(2)}</span>
              {cost.model && <span className="text-rw-dim">· {cost.model}</span>}
            </span>
          )}
        </header>

        {/* Verdict hero */}
        <VerdictHero report={report} />

        {/* Severity bar + CVSS/EPSS scatter */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SeverityBar counts={counts} />
          <CvssEpssScatter findings={report.findings ?? []} />
        </div>

        {/* Scan context — scope/objective/methodology + recon metadata */}
        {(report.objective?.trim() ||
          report.scope?.trim() ||
          report.methodology?.trim() ||
          report.total_endpoints > 0 ||
          (report.agents_executed?.length ?? 0) > 0 ||
          (report.tools_used?.length ?? 0) > 0) && (
          <section>
            <SectionTitle>Scan Context</SectionTitle>
            <div className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-rw-border bg-rw-border sm:grid-cols-2">
              {report.objective?.trim() && <ContextRow label="Objective" value={report.objective} />}
              {report.scope?.trim() && <ContextRow label="Scope" value={report.scope} />}
              {report.total_endpoints > 0 && (
                <ContextRow label="Endpoints discovered" value={String(report.total_endpoints)} />
              )}
              {(report.discovered_services?.length ?? 0) > 0 && (
                <ContextRow label="Services discovered" value={String(report.discovered_services.length)} />
              )}
              {(report.agents_executed?.length ?? 0) > 0 && (
                <ContextRow label="Agents executed" value={report.agents_executed.join(", ")} />
              )}
              {(report.tools_used?.length ?? 0) > 0 && (
                <ContextRow label="Tools used" value={report.tools_used.join(", ")} />
              )}
            </div>
            {report.methodology?.trim() && (
              <div className="mt-3 rounded-xl border border-rw-border bg-rw-elevated p-4">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-rw-dim">
                  Methodology
                </div>
                <div className="whitespace-pre-line text-sm leading-relaxed text-rw-muted">
                  {report.methodology.trim()}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Discovered surface — recon results (services + technologies) */}
        {((report.discovered_services?.length ?? 0) > 0 ||
          (report.discovered_technologies?.length ?? 0) > 0) && (
          <section>
            <SectionTitle>Discovered Surface</SectionTitle>
            <div className="space-y-4 rounded-xl border border-rw-border bg-rw-elevated p-4">
              {(report.discovered_services?.length ?? 0) > 0 && (
                <div className="space-y-1.5">
                  {report.discovered_services.map((s, i) => (
                    <div
                      key={`${s.host}:${s.port ?? ""}:${i}`}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-rw-border-subtle bg-rw-surface/30 px-3 py-2 text-sm"
                    >
                      <span className="font-mono text-rw-text">
                        {s.host}
                        {s.port != null ? `:${s.port}` : ""}
                      </span>
                      {s.service && <span className="text-rw-muted">{s.service}</span>}
                      {s.version && <span className="text-xs text-rw-dim">{s.version}</span>}
                      {s.status_code != null && (
                        <span className="ml-auto rounded bg-rw-surface px-1.5 py-0.5 text-[11px] tabular-nums text-rw-dim">
                          {s.status_code}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {(report.discovered_technologies?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {report.discovered_technologies.map((t) => (
                    <span
                      key={t}
                      className="rounded-md border border-rw-border-subtle bg-rw-surface/40 px-2 py-0.5 text-xs text-rw-muted"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </section>
        )}

        {/* Attack paths */}
        <section>
          <SectionTitle>Attack Paths</SectionTitle>
          <AttackPathGraph chains={chains} />
        </section>

        {/* Unified attack graph (target -> host -> service -> CVE -> exploit) */}
        {runId && (
          <section>
            <SectionTitle>Attack Surface Graph</SectionTitle>
            <AttackGraphView runId={runId} />
          </section>
        )}

        {/* MITRE ATT&CK heatmap */}
        <section>
          <div className="mb-3 flex items-center justify-between gap-3">
            <SectionTitle>Framework Coverage</SectionTitle>
            {runId && (
              <button
                onClick={openCoverageInNavigator}
                className="inline-flex items-center gap-1.5 rounded-md border border-rw-border px-2.5 py-1 text-xs text-rw-muted transition-colors hover:text-rw-text"
              >
                <ExternalLink size={13} /> Open in ATT&CK Navigator
              </button>
            )}
          </div>
          <MitreHeatmap techniques={mitre} />
        </section>

        {/* OWASP Top 10 compliance */}
        {owasp.length > 0 && (
          <section>
            <SectionTitle>OWASP Top 10</SectionTitle>
            <div className="grid grid-cols-1 gap-2 rounded-xl border border-rw-border bg-rw-elevated p-4 sm:grid-cols-2">
              {owasp.map((o) => (
                <div
                  key={o.category}
                  className="flex items-center justify-between gap-3 rounded-lg border border-rw-border-subtle bg-rw-surface/30 px-3 py-2"
                >
                  <span className="min-w-0 truncate text-sm text-rw-text">{o.category}</span>
                  <span
                    className={cn(
                      "shrink-0 rounded px-2 py-0.5 text-xs font-bold tabular-nums",
                      o.count > 0 ? "text-rw-text" : "text-rw-dim",
                    )}
                    style={o.count > 0 ? { background: "var(--color-rw-surface)" } : undefined}
                  >
                    {o.count}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Remediation priorities */}
        {priorities.length > 0 && (
          <section>
            <SectionTitle>Remediation Priorities</SectionTitle>
            <ol className="space-y-2 rounded-xl border border-rw-border bg-rw-elevated p-4">
              {priorities.map((p, i) => (
                <li
                  key={p.finding_id || i}
                  className="flex items-start gap-3 rounded-lg border border-rw-border-subtle bg-rw-surface/30 p-3"
                >
                  <span
                    className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold tabular-nums text-rw-bg"
                    style={{ background: severityHex((p.severity || "info").toLowerCase()) }}
                  >
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium text-rw-text">{p.title}</span>
                      <SeverityBadge severity={(p.severity || "info").toLowerCase() as Finding["severity"]} />
                      {p.cvss_score != null && (
                        <span className="text-[11px] text-rw-dim">CVSS {p.cvss_score.toFixed(1)}</span>
                      )}
                    </div>
                    {p.remediation && <p className="mt-1 text-xs text-rw-muted">{p.remediation}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* LLM narrative */}
        {markdown.trim() && (
          <section>
            <SectionTitle>
              <span className="inline-flex items-center gap-1.5">
                <ListChecks size={14} /> Full Report
              </span>
            </SectionTitle>
            <div className="rounded-xl border border-rw-border bg-rw-elevated p-6">
              <MarkdownRenderer content={markdown} variant="enhanced" />
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
