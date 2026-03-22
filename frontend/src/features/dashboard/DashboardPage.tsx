import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Target, Activity, AlertTriangle, Plus, ExternalLink } from "lucide-react";
import { formatRelativeDate } from "../../utils/formatDate";
import { severityHex, SEVERITY_ORDER } from "../../config/theme";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import { PageHeader } from "../../components/layout/PageHeader";
import { api } from "../../services/api";
import type { RunSummary, Finding } from "../../types/api";

export function DashboardPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allFindings, setAllFindings] = useState<Finding[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchRuns = () => {
    api.runs.list().then(setRuns).catch(() => {});
  };

  useEffect(() => { fetchRuns(); }, []);

  useEffect(() => {
    const finishedRuns = runs.filter((r) => r.status === "completed" || r.status === "failed").slice(0, 5);
    if (finishedRuns.length === 0) { setAllFindings([]); return; }
    Promise.all(
      finishedRuns.map((r) =>
        api.runs.findings(r.run_id)
          .then((findings) => findings.map((f) => ({ ...f, _target: r.target })))
          .catch(() => [] as Finding[]),
      ),
    ).then((results) => setAllFindings(results.flat()));
  }, [runs]);

  const hasActive = runs.some((r) => r.status === "running" || r.status === "queued");
  useEffect(() => {
    if (hasActive) pollRef.current = setInterval(fetchRuns, 5000);
    else if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [hasActive]);

  const running = runs.filter((r) => r.status === "running").length;
  const completed = runs.filter((r) => r.status === "completed").length;
  const failed = runs.filter((r) => r.status === "failed").length;

  const sevCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of SEVERITY_ORDER) counts[s] = 0;
    for (const f of allFindings) counts[f.severity] = (counts[f.severity] || 0) + 1;
    return counts;
  }, [allFindings]);

  const recentFindings = useMemo(
    () => [...allFindings].sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || "")).slice(0, 8),
    [allFindings],
  );

  const stats = [
    { label: "Total Hunts", value: runs.length, icon: Target, color: "text-rw-accent" },
    { label: "Running", value: running, icon: Activity, color: "text-blue-400" },
    { label: "Completed", value: completed, icon: Shield, color: "text-emerald-400" },
    { label: "Failed", value: failed, icon: AlertTriangle, color: "text-red-400" },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6 animate-fade-in">
      <PageHeader
        title="Dashboard"
        actions={
          <Button icon={<Plus size={16} />} onClick={() => navigate("/hunt")}>
            New Hunt
          </Button>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map((s) => (
          <Card key={s.label}>
            <div className="flex items-center gap-3">
              <s.icon size={20} className={s.color} />
              <div>
                <div className="text-2xl font-bold text-rw-text">{s.value}</div>
                <div className="text-xs text-rw-dim">{s.label}</div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Vulnerability Overview */}
      {allFindings.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider mb-3">
            Vulnerability Overview
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <Card>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-sm font-medium text-rw-text">Severity Breakdown</span>
                <span className="text-xs text-rw-dim ml-auto">{allFindings.length} total</span>
              </div>
              <div className="space-y-2">
                {SEVERITY_ORDER.map((sev) => {
                  const count = sevCounts[sev] || 0;
                  const pct = allFindings.length > 0 ? (count / allFindings.length) * 100 : 0;
                  return (
                    <div key={sev} className="flex items-center gap-3">
                      <span className="text-xs text-rw-muted w-16 capitalize">{sev}</span>
                      <div className="flex-1 h-2 bg-rw-surface rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%`, background: severityHex(sev) }}
                        />
                      </div>
                      <span className="text-xs text-rw-muted w-8 text-right">{count}</span>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card>
              <span className="text-sm font-medium text-rw-text block mb-3">Latest Findings</span>
              <div className="space-y-1">
                {recentFindings.map((f, i) => (
                  <div key={f.id || i} className="flex items-center gap-2 py-1 text-sm">
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: severityHex(f.severity) }} />
                    <span className="text-rw-text truncate flex-1">{f.title}</span>
                    <SeverityBadge severity={f.severity} />
                  </div>
                ))}
                {recentFindings.length === 0 && <span className="text-xs text-rw-dim">No findings yet</span>}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* Hunt List */}
      <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider mb-3">Hunts</h2>
      {runs.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Target size={32} />}
            title="No hunts yet"
            description="Start one from the Hunt tab."
          />
        </Card>
      ) : (
        <Card padding="none">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rw-border">
                <th className="text-left text-xs text-rw-dim font-medium py-2.5 px-4">Status</th>
                <th className="text-left text-xs text-rw-dim font-medium py-2.5 px-4">Target</th>
                <th className="text-left text-xs text-rw-dim font-medium py-2.5 px-4">Created</th>
                <th className="text-left text-xs text-rw-dim font-medium py-2.5 px-4">Run ID</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.run_id}
                  onClick={() => navigate(`/hunt/${run.run_id}`)}
                  className="border-b border-rw-border-subtle hover:bg-rw-surface cursor-pointer transition-colors"
                >
                  <td className="py-2.5 px-4">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="py-2.5 px-4 text-rw-text font-mono text-xs">{run.target}</td>
                  <td className="py-2.5 px-4 text-rw-dim">{formatRelativeDate(run.created_at)}</td>
                  <td className="py-2.5 px-4 text-rw-dim font-mono text-xs">{run.run_id.slice(0, 8)}</td>
                  <td className="py-2.5 px-4">
                    <ExternalLink size={14} className="text-rw-dim" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
