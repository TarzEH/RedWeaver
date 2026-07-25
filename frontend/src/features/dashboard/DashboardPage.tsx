import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, Target, Activity, AlertTriangle, Plus, ExternalLink } from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
} from "recharts";
import { formatRelativeDate } from "../../utils/formatDate";
import { severityHex, SEVERITY_ORDER } from "../../config/theme";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { SeverityBadge } from "../../components/ui/SeverityBadge";
import { isRuledOut } from "../../components/ui/FindingStatusBadge";
import { EmptyState } from "../../components/ui/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";
import { Table, THead, TBody, TH, TR, TD } from "../../components/ui/Table";
import { PageHeader } from "../../components/layout/PageHeader";
import { api } from "../../services/api";
import type { RunSummary, Finding } from "../../types/api";

/** Finding rows are tagged with the originating run's target for trend grouping. */
type TaggedFinding = Finding & { _target?: string; _runId?: string; _created?: string };

export function DashboardPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [allFindings, setAllFindings] = useState<TaggedFinding[]>([]);
  const [runsLoading, setRunsLoading] = useState(true);
  const [findingsLoading, setFindingsLoading] = useState(true);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Skeletons belong to the very first findings load only — see the effect below.
  const findingsFetchedRef = useRef(false);

  const fetchRuns = () => {
    api.runs.list().then(setRuns).catch(() => {}).finally(() => setRunsLoading(false));
  };

  useEffect(() => { fetchRuns(); }, []);

  const finishedRuns = useMemo(
    () => runs.filter((r) => r.status === "completed" || r.status === "failed").slice(0, 5),
    [runs],
  );
  // The 5s poll hands back a brand-new array every time, so `runs` changes identity
  // even when the data is unchanged. Key the findings refetch on the finished runs'
  // identity+status instead — a primitive that only moves when a refetch is warranted.
  const finishedKey = useMemo(
    () => finishedRuns.map((r) => `${r.run_id}:${r.status}`).join("|"),
    [finishedRuns],
  );
  // Read through a ref so the effect can use the current rows without depending on
  // the array identity (target/created_at are fixed for a given run id).
  const finishedRunsRef = useRef(finishedRuns);
  finishedRunsRef.current = finishedRuns;

  useEffect(() => {
    const targets = finishedRunsRef.current;
    if (targets.length === 0) { setAllFindings([]); setFindingsLoading(false); return; }
    // Only the first load may swap in skeletons; a background refresh keeps the
    // charts mounted, otherwise recharts replays its entry animation on remount.
    if (!findingsFetchedRef.current) setFindingsLoading(true);
    let ignore = false;
    Promise.all(
      targets.map((r) =>
        api.runs.findings(r.run_id)
          .then((findings) =>
            findings.map(
              (f): TaggedFinding => ({
                ...f,
                _target: r.target,
                _runId: r.run_id,
                _created: r.created_at,
              }),
            ),
          )
          .catch(() => [] as TaggedFinding[]),
      ),
    )
      // Overlapping polls can resolve out of order — drop superseded responses.
      // Findings the verifier refuted are excluded here, the same way the report
      // and the triage page exclude them. Otherwise the dashboard headlines a
      // finding as CRITICAL while the findings page shows it struck through as
      // ruled out — and the portfolio-level severity counts overstate the risk.
      .then((results) => {
        if (!ignore) setAllFindings(results.flat().filter((f) => !isRuledOut(f.status)));
      })
      .finally(() => {
        if (ignore) return;
        findingsFetchedRef.current = true;
        setFindingsLoading(false);
      });
    return () => { ignore = true; };
  }, [finishedKey]);

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

  const donutData = useMemo(
    () => SEVERITY_ORDER.map((s) => ({ name: s, value: sevCounts[s] || 0 })).filter((d) => d.value > 0),
    [sevCounts],
  );

  // Findings-by-severity across the recent finished runs, ordered chronologically
  // so the trend reads left→right (oldest → newest run).
  const trendData = useMemo(() => {
    const byRun = new Map<string, { label: string; created: string; counts: Record<string, number> }>();
    for (const f of allFindings) {
      const runId = f._runId || "unknown";
      let entry = byRun.get(runId);
      if (!entry) {
        const zero: Record<string, number> = {};
        for (const s of SEVERITY_ORDER) zero[s] = 0;
        entry = { label: f._target || runId.slice(0, 8), created: f._created || "", counts: zero };
        byRun.set(runId, entry);
      }
      entry.counts[f.severity] = (entry.counts[f.severity] || 0) + 1;
    }
    return [...byRun.values()]
      .sort((a, b) => (a.created || "").localeCompare(b.created || ""))
      .map((e) => ({ name: e.label, ...e.counts }));
  }, [allFindings]);

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
        {runsLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <div className="flex items-center gap-3">
                  <Skeleton className="h-5 w-5 rounded" />
                  <div className="space-y-1.5">
                    <Skeleton className="h-7 w-10" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
              </Card>
            ))
          : stats.map((s) => (
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

      {/* Vulnerability Overview — skeleton while findings load */}
      {findingsLoading && !runsLoading && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider mb-3">
            Vulnerability Overview
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i}>
                <Skeleton className="mb-3 h-4 w-32" />
                <Skeleton className="h-40 w-full" />
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Vulnerability Overview */}
      {!findingsLoading && allFindings.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider mb-3">
            Vulnerability Overview
          </h2>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card>
              <span className="mb-2 block text-sm font-medium text-rw-text">Severity Distribution</span>
              <div className="relative">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={52}
                      outerRadius={78}
                      paddingAngle={2}
                      stroke="none"
                    >
                      {donutData.map((d) => (
                        <Cell key={d.name} fill={severityHex(d.name)} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#111827",
                        border: "1px solid #334155",
                        borderRadius: 8,
                        fontSize: 12,
                        textTransform: "capitalize",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-rw-text">{allFindings.length}</span>
                  <span className="text-[10px] uppercase tracking-wide text-rw-dim">findings</span>
                </div>
              </div>
            </Card>

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

          {/* Findings over time — by-severity across the recent finished runs */}
          <Card className="mt-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-sm font-medium text-rw-text">Findings Over Time</span>
              <span className="text-xs text-rw-dim">
                {trendData.length} run{trendData.length === 1 ? "" : "s"}
              </span>
            </div>
            {trendData.length < 2 ? (
              <p className="py-6 text-center text-xs text-rw-dim">
                Findings trend appears once two or more finished runs are available.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={trendData} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" />
                  <YAxis tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" width={36} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: "#111827",
                      border: "1px solid #334155",
                      borderRadius: 8,
                      fontSize: 12,
                      textTransform: "capitalize",
                    }}
                  />
                  {SEVERITY_ORDER.map((sev) => (
                    <Area
                      key={sev}
                      type="monotone"
                      dataKey={sev}
                      stackId="sev"
                      stroke={severityHex(sev)}
                      fill={severityHex(sev)}
                      fillOpacity={0.55}
                      strokeWidth={1}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Card>
        </div>
      )}

      {/* Hunt List */}
      <h2 className="text-sm font-medium text-rw-muted uppercase tracking-wider mb-3">Hunts</h2>
      {/* `runsLoading` only ever goes true → false on the first load, so the
          5s poll can never flip this back to a skeleton. */}
      {runsLoading ? (
        <Card padding="sm" className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </Card>
      ) : runs.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Target size={32} />}
            title="No hunts yet"
            description="Start one from the Hunt tab."
          />
        </Card>
      ) : (
        <Card padding="none" className="overflow-hidden">
          <Table>
            <THead>
              <tr>
                <TH>Status</TH>
                <TH>Target</TH>
                <TH>Created</TH>
                <TH>Run ID</TH>
                <TH className="w-10">
                  <span className="sr-only">Open</span>
                </TH>
              </tr>
            </THead>
            <TBody>
              {runs.map((run) => (
                <TR
                  key={run.run_id}
                  interactive
                  role="button"
                  tabIndex={0}
                  aria-label={`Open hunt for ${run.target}`}
                  onClick={() => navigate(`/hunt/${run.run_id}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      navigate(`/hunt/${run.run_id}`);
                    }
                  }}
                >
                  <TD>
                    <StatusBadge status={run.status} />
                  </TD>
                  <TD className="font-mono text-xs text-rw-text">{run.target}</TD>
                  <TD className="text-rw-dim">{formatRelativeDate(run.created_at)}</TD>
                  <TD className="font-mono text-xs tabular-nums text-rw-dim">
                    {run.run_id.slice(0, 8)}
                  </TD>
                  <TD>
                    <ExternalLink size={14} aria-hidden className="text-rw-dim" />
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
