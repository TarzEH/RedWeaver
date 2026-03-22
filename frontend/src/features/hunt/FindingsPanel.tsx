import { useEffect, useMemo, useState } from "react";
import { Shield, ChevronDown, ChevronRight, ExternalLink, Search } from "lucide-react";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
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

export function FindingsPanel({ runId, compact = false }: FindingsPanelProps) {
  const [apiFindings, setApiFindings] = useState<Finding[]>([]);
  const [filter, setFilter] = useState<Severity | "all">("all");
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
    const byId = new Map<string, Finding>();
    for (const f of apiFindings) byId.set(f.id, f);
    for (const f of sseFindings) byId.set(f.id, f);
    return Array.from(byId.values());
  }, [apiFindings, sseFindings]);

  const toggleExpand = (id: string) =>
    setExpandedIds((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  const sorted = [...findings].sort((a, b) => (SEV_PRIORITY[a.severity] ?? 4) - (SEV_PRIORITY[b.severity] ?? 4));
  const searched = searchQuery
    ? sorted.filter((f) => f.title.toLowerCase().includes(searchQuery.toLowerCase()) || f.description.toLowerCase().includes(searchQuery.toLowerCase()))
    : sorted;
  const filtered = filter === "all" ? searched : searched.filter((f) => f.severity === filter);

  const counts: Record<string, number> = { all: findings.length };
  for (const s of ALL_SEVERITIES) counts[s] = findings.filter((f) => f.severity === s).length;

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
          <span className="text-xs text-rw-dim">{findings.length}</span>
        </div>
        {loading ? (
          <p className="text-xs text-rw-dim">Loading...</p>
        ) : findings.length === 0 ? (
          <p className="text-xs text-rw-dim">No findings yet.</p>
        ) : (
          <div className="space-y-1">
            {sorted.slice(0, 20).map((f) => (
              <div key={f.id} className="flex items-center gap-2 py-1 text-xs">
                <SeverityBadge severity={f.severity} />
                <span className="text-rw-text truncate">{f.title}</span>
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
        <span className="text-sm text-rw-dim">{findings.length} total</span>
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
      </div>

      {loading ? (
        <p className="text-sm text-rw-dim">Loading findings...</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-rw-dim">
          No findings{filter !== "all" ? ` with severity "${filter}"` : ""}
          {searchQuery ? ` matching "${searchQuery}"` : ""}.
        </p>
      ) : (
        <div className="space-y-1">
          {filtered.map((f) => {
            const isExpanded = expandedIds.has(f.id);
            return (
              <div key={f.id} className="bg-rw-elevated border border-rw-border rounded-xl overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggleExpand(f.id)}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-rw-surface transition-colors"
                >
                  {isExpanded ? <ChevronDown size={14} className="text-rw-dim shrink-0" /> : <ChevronRight size={14} className="text-rw-dim shrink-0" />}
                  <SeverityBadge severity={f.severity} />
                  <span className="text-sm text-rw-text truncate flex-1">{f.title}</span>
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
                          <span key={cve} className="text-[10px] font-mono bg-rw-surface text-rw-muted px-1.5 py-0.5 rounded">
                            {cve}
                          </span>
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
