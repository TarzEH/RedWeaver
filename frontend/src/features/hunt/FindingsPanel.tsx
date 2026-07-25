import { useEffect, useMemo, useState } from "react";
import { Shield, ChevronDown, ChevronRight, ExternalLink, Search, Eye, EyeOff } from "lucide-react";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { FindingStatusBadge, isRuledOut } from "../../components/ui/FindingStatusBadge";
import { Input } from "../../components/ui/Input";
import { EmptyState } from "../../components/ui/EmptyState";
import { useHuntContext } from "../../contexts/HuntContext";
import { api } from "../../services/api";
import type { Finding, Severity } from "../../types/api";

interface FindingsPanelProps {
  runId: string | null;
  compact?: boolean;
}

const ALL_SEVERITIES: Severity[] = ["critical", "high", "medium", "low", "info"];
const SEV_PRIORITY: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

// SSVC decision colors (Act = remediate now ... Track = no action now).
const SSVC_CLS: Record<string, string> = {
  act: "text-rw-danger border-rw-danger/40",
  attend: "text-orange-400 border-orange-500/40",
  "track*": "text-yellow-400 border-yellow-500/40",
  track: "text-rw-dim border-rw-border",
};

export function FindingsPanel({ runId, compact = false }: FindingsPanelProps) {
  const [apiFindings, setApiFindings] = useState<Finding[]>([]);
  const [filter, setFilter] = useState<Severity | "all">("all");
  // Default: hide what the verifier refuted — that matches the pipeline's delivered output.
  const [hideRuledOut, setHideRuledOut] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const { findings: sseFindings, done: streamDone } = useHuntContext();

  useEffect(() => {
    if (!runId) {
      setApiFindings([]);
      return;
    }
    setApiFindings([]);
    setExpandedIds(new Set());
    setLoading(true);
    api.runs
      .findings(runId)
      .then(setApiFindings)
      .catch(() => setApiFindings([]))
      .finally(() => setLoading(false));
  }, [runId, streamDone]);

  const findings = useMemo(() => {
    // Once the run is over the persisted table is the system of record: the
    // engine publishes a finding event *before* the recorder applies its dedup
    // check, so the stream retains emissions that were never stored. Keeping
    // them would over-count a finished run against its own report.
    const live = !streamDone || apiFindings.length === 0 ? sseFindings : [];

    // Key on the backend's own dedup key, not on `id`: several agents report
    // the same issue and each emission carries its own uuid, while the backend
    // collapses them into one row. Without this, a finding shows up once per
    // agent that mentioned it, and a refuted one sneaks back via a stream twin
    // that has no `status`. Stream first so the persisted copy wins — only it
    // carries the verifier's verdict and the triage state.
    const byKey = new Map<string, Finding>();
    for (const f of [...live, ...apiFindings]) {
      byKey.set(
        `${(f.title || "").toLowerCase().trim()}|${(f.affected_url || "").toLowerCase().trim()}|${f.severity}`,
        f,
      );
    }
    return Array.from(byKey.values());
  }, [apiFindings, sseFindings, streamDone]);

  const toggleExpand = (id: string) =>
    setExpandedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const ruledOutCount = findings.filter((f) => isRuledOut(f.status)).length;
  /** The population every list and facet count below describes. */
  const population = hideRuledOut ? findings.filter((f) => !isRuledOut(f.status)) : findings;
  const excludingRuledOut = hideRuledOut && ruledOutCount > 0;

  // Ruled-out findings (when shown) sink below live ones, then severity order.
  const sorted = [...population].sort(
    (a, b) =>
      Number(isRuledOut(a.status)) - Number(isRuledOut(b.status)) ||
      (SEV_PRIORITY[a.severity] ?? 4) - (SEV_PRIORITY[b.severity] ?? 4),
  );
  const searched = searchQuery
    ? sorted.filter((f) => f.title.toLowerCase().includes(searchQuery.toLowerCase()) || f.description.toLowerCase().includes(searchQuery.toLowerCase()))
    : sorted;
  const filtered = filter === "all" ? searched : searched.filter((f) => f.severity === filter);

  const counts: Record<string, number> = { all: population.length };
  for (const s of ALL_SEVERITIES) counts[s] = population.filter((f) => f.severity === s).length;

  if (!runId) {
    return (
      <EmptyState icon={<Shield size={compact ? 20 : 28} />} title="Select a hunt to view findings." compact={compact} />
    );
  }

  if (compact) {
    return (
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-rw-muted">Findings</span>
          <div className="flex items-center gap-2">
            {ruledOutCount > 0 && (
              <button
                type="button"
                onClick={() => setHideRuledOut((v) => !v)}
                aria-pressed={hideRuledOut}
                title={
                  hideRuledOut
                    ? `${ruledOutCount} finding(s) the verifier refuted are hidden — show them`
                    : `Hide the ${ruledOutCount} finding(s) the verifier refuted`
                }
                className="inline-flex items-center gap-1 text-[10px] text-rw-dim hover:text-rw-muted transition-colors"
              >
                {hideRuledOut ? <EyeOff size={10} /> : <Eye size={10} />}
                {ruledOutCount} ruled out
              </button>
            )}
            <span className="text-xs text-rw-dim" title={excludingRuledOut ? "Excludes ruled-out findings" : "All findings"}>
              {population.length}
            </span>
          </div>
        </div>
        {loading ? (
          <p className="text-xs text-rw-dim">Loading...</p>
        ) : population.length === 0 ? (
          <p className="text-xs text-rw-dim">
            {findings.length === 0 ? "No findings yet." : `All ${ruledOutCount} findings ruled out.`}
          </p>
        ) : (
          <div className="space-y-1">
            {sorted.slice(0, 20).map((f) => (
              <div key={f.id} className="flex items-center gap-2 py-1 text-xs">
                <SeverityBadge severity={f.severity} className={isRuledOut(f.status) ? "opacity-50 grayscale" : ""} />
                <FindingStatusBadge status={f.status} verifiedBy={f.verified_by_agent} compact />
                <span
                  className={`truncate flex-1 ${
                    isRuledOut(f.status) ? "text-rw-dim line-through decoration-rw-dim/70" : "text-rw-text"
                  }`}
                >
                  {f.title}
                </span>
                {f.cisa_kev && <span className="text-[9px] font-semibold text-rw-danger shrink-0" title="CISA KEV">KEV</span>}
                {f.risk_decision && (
                  <span
                    title={`Risk ${f.risk_score} · SSVC ${f.risk_decision}`}
                    className={`shrink-0 rounded border px-1 py-0.5 text-[9px] font-medium uppercase ${SSVC_CLS[f.risk_decision] || "text-rw-dim border-rw-border"}`}
                  >
                    {f.risk_decision}
                  </span>
                )}
              </div>
            ))}
            {sorted.length > 20 && <p className="text-[10px] text-rw-dim">+{sorted.length - 20} more</p>}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-rw-text flex items-center gap-2">
          <Shield size={20} /> Findings
        </h2>
        <span className="text-sm text-rw-dim">
          {excludingRuledOut ? `${population.length} shown · ${ruledOutCount} ruled out` : `${findings.length} total`}
        </span>
      </div>

      <Input
        icon={<Search size={14} />}
        placeholder="Search findings..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        className="mb-3"
      />

      {/* Filter pills */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <button
          onClick={() => setFilter("all")}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            filter === "all" ? "bg-rw-accent/15 text-rw-accent" : "bg-rw-surface text-rw-dim hover:text-rw-muted"
          }`}
        >
          All ({counts.all})
        </button>
        {ALL_SEVERITIES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize ${
              filter === s ? "bg-rw-accent/15 text-rw-accent" : "bg-rw-surface text-rw-dim hover:text-rw-muted"
            }`}
          >
            {s} ({counts[s]})
          </button>
        ))}
        {ruledOutCount > 0 && (
          <button
            onClick={() => setHideRuledOut((v) => !v)}
            aria-pressed={hideRuledOut}
            title={
              hideRuledOut
                ? "Findings the verifier refuted are hidden — click to show them"
                : "Findings the verifier refuted are shown — click to hide them"
            }
            className={`ml-auto inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              hideRuledOut ? "bg-rw-accent/15 text-rw-accent" : "bg-rw-surface text-rw-dim hover:text-rw-muted"
            }`}
          >
            {hideRuledOut ? <EyeOff size={12} /> : <Eye size={12} />}
            Hide ruled out ({ruledOutCount})
          </button>
        )}
      </div>

      {ruledOutCount > 0 && (
        <p className="-mt-3 mb-4 text-[11px] text-rw-dim">
          Counts above {hideRuledOut ? "exclude" : "include"} {ruledOutCount} finding
          {ruledOutCount === 1 ? "" : "s"} the verifier ruled out as false positive
          {ruledOutCount === 1 ? "" : "s"}.
        </p>
      )}

      {loading ? (
        <p className="text-sm text-rw-dim">Loading findings...</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-rw-dim">
          No findings{filter !== "all" ? ` with severity "${filter}"` : ""}
          {searchQuery ? ` matching "${searchQuery}"` : ""}.
          {excludingRuledOut ? ` ${ruledOutCount} ruled-out finding${ruledOutCount === 1 ? " is" : "s are"} hidden.` : ""}
        </p>
      ) : (
        <div className="space-y-1">
          {filtered.map((f) => {
            const isExpanded = expandedIds.has(f.id);
            const ruledOut = isRuledOut(f.status);
            return (
              <div
                key={f.id}
                className={`bg-rw-elevated border rounded-xl overflow-hidden ${
                  ruledOut ? "border-dashed border-rw-border/60" : "border-rw-border"
                }`}
              >
                <button
                  type="button"
                  onClick={() => toggleExpand(f.id)}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-rw-surface transition-colors"
                >
                  {isExpanded ? <ChevronDown size={14} className="text-rw-dim shrink-0" /> : <ChevronRight size={14} className="text-rw-dim shrink-0" />}
                  <SeverityBadge severity={f.severity} className={ruledOut ? "opacity-50 grayscale" : ""} />
                  <FindingStatusBadge status={f.status} verifiedBy={f.verified_by_agent} />
                  <span
                    className={`text-sm truncate flex-1 ${
                      ruledOut ? "text-rw-dim line-through decoration-rw-dim/70" : "text-rw-text"
                    }`}
                  >
                    {f.title}
                  </span>
                  {f.cisa_kev && (
                    <span className="text-[10px] font-semibold text-rw-danger shrink-0" title="CISA Known Exploited Vulnerability">KEV</span>
                  )}
                  {f.risk_decision && (
                    <span
                      title={`Risk ${f.risk_score} · SSVC ${f.risk_decision}`}
                      className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${SSVC_CLS[f.risk_decision] || "text-rw-dim border-rw-border"}`}
                    >
                      {f.risk_decision} {f.risk_score}
                    </span>
                  )}
                  <span className="text-[10px] text-rw-dim shrink-0">{f.agent_source}</span>
                  {f.cvss_score != null && <span className="text-[10px] font-mono text-rw-muted shrink-0">CVSS {f.cvss_score}</span>}
                </button>

                {isExpanded && (
                  <div className="px-3 pb-3 border-t border-rw-border-subtle space-y-3 animate-fade-in">
                    {f.description && <p className="text-sm text-rw-muted pt-2">{f.description}</p>}
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {f.affected_url && (
                        <div>
                          <span className="text-rw-dim block mb-0.5">Affected URL</span>
                          <span className="text-rw-text font-mono flex items-center gap-1">
                            <ExternalLink size={10} />
                            {f.affected_url}
                          </span>
                        </div>
                      )}
                      {f.tool_used && (
                        <div>
                          <span className="text-rw-dim block mb-0.5">Tool</span>
                          <span className="text-rw-text font-mono">{f.tool_used}</span>
                        </div>
                      )}
                      {f.exploitability && f.exploitability !== "unknown" && (
                        <div>
                          <span className="text-rw-dim block mb-0.5">Exploitability</span>
                          <span className="text-rw-text capitalize">{f.exploitability}</span>
                        </div>
                      )}
                      {f.epss_score != null && (
                        <div>
                          <span className="text-rw-dim block mb-0.5" title="Exploit Prediction Scoring System — likelihood of exploitation in the wild (next 30 days)">EPSS</span>
                          <span className="text-rw-text tabular-nums">{(f.epss_score * 100).toFixed(1)}%</span>
                        </div>
                      )}
                      {f.confidence != null && (
                        <div>
                          <span className="text-rw-dim block mb-0.5" title="Corroborating-signal confidence">Confidence</span>
                          <span className="text-rw-text tabular-nums">{Math.round(f.confidence * 100)}%</span>
                        </div>
                      )}
                    </div>
                    {f.evidence && (
                      <div>
                        <span className="text-xs text-rw-dim block mb-1">Evidence</span>
                        <pre className="text-xs font-mono text-rw-muted bg-rw-surface rounded-lg p-3 overflow-x-auto max-h-32 whitespace-pre-wrap">
                          {f.evidence}
                        </pre>
                      </div>
                    )}
                    {f.remediation && (
                      <div>
                        <span className="text-xs text-emerald-400 block mb-1">Remediation</span>
                        <p className="text-sm text-rw-muted">{f.remediation}</p>
                      </div>
                    )}
                    {f.cve_ids.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {f.cve_ids.map((cve) => (
                          <a
                            key={cve}
                            href={`https://nvd.nist.gov/vuln/detail/${encodeURIComponent(cve)}`}
                            target="_blank"
                            rel="noreferrer"
                            title="Open on NVD"
                            className="text-[10px] font-mono bg-rw-surface text-rw-muted px-1.5 py-0.5 rounded hover:text-rw-text transition-colors"
                          >
                            {cve}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
