import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { GitCompareArrows, Plus, RefreshCw, Check, Inbox } from "lucide-react";
import { api } from "../../services/api";
import type { RunCompare } from "../../services/api";
import type { Finding, RunSummary, Severity } from "../../types/api";
import { SEVERITY_ORDER, severityHex, severityStyle } from "../../config/theme";
import { Spinner } from "../../components/ui/Spinner";
import { EmptyState } from "../../components/ui/EmptyState";
import { cn } from "../../lib/cn";

type DeltaKind = "new" | "recurring" | "fixed";

const COLUMN_CONFIG: Record<
  DeltaKind,
  { label: string; hex: string; ring: string; accentText: string; icon: typeof Plus }
> = {
  new: {
    label: "New",
    hex: "#ef4444",
    ring: "border-red-500/30",
    accentText: "text-red-400",
    icon: Plus,
  },
  recurring: {
    label: "Recurring",
    hex: "#f59e0b",
    ring: "border-amber-500/30",
    accentText: "text-amber-400",
    icon: RefreshCw,
  },
  fixed: {
    label: "Fixed",
    hex: "#10b981",
    ring: "border-emerald-500/30",
    accentText: "text-emerald-400",
    icon: Check,
  },
};

function normSeverity(value: string): Severity {
  const v = value?.toLowerCase() as Severity;
  return SEVERITY_ORDER.includes(v) ? v : "info";
}

function FindingRow({ finding }: { finding: Finding }) {
  const sev = normSeverity(finding.severity);
  const s = severityStyle(sev);
  return (
    <li className="flex items-start gap-2.5 rounded-lg border border-rw-border bg-rw-elevated px-3 py-2.5">
      <span
        className={cn(
          "mt-0.5 inline-flex shrink-0 items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide",
          s.bg,
          s.color,
          s.border,
        )}
      >
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: severityHex(sev) }}
          aria-hidden
        />
        {s.label}
      </span>
      <span className="min-w-0 flex-1 text-sm text-rw-text">
        {finding.title || "(untitled finding)"}
        {finding.affected_url && (
          <span className="mt-0.5 block truncate font-mono text-[11px] text-rw-dim">
            {finding.affected_url}
          </span>
        )}
      </span>
    </li>
  );
}

function DeltaColumn({ kind, findings }: { kind: DeltaKind; findings: Finding[] }) {
  const cfg = COLUMN_CONFIG[kind];
  const Icon = cfg.icon;
  return (
    <div className={cn("flex flex-col rounded-xl border bg-rw-elevated/40", cfg.ring)}>
      <div className="flex items-center gap-2 border-b border-rw-border px-4 py-3">
        <Icon size={15} className={cfg.accentText} />
        <h3 className={cn("text-sm font-semibold", cfg.accentText)}>{cfg.label}</h3>
        <span className="ml-auto font-mono text-xs font-semibold text-rw-muted">
          {findings.length}
        </span>
      </div>
      <div className="flex-1 p-3">
        {findings.length === 0 ? (
          <EmptyState compact icon={<Inbox size={20} />} title="None" />
        ) : (
          <ul className="flex flex-col gap-2">
            {findings.map((f) => (
              <FindingRow key={f.id} finding={f} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SummaryTile({ kind, value }: { kind: DeltaKind; value: number }) {
  const cfg = COLUMN_CONFIG[kind];
  return (
    <div
      className="rounded-xl border border-rw-border bg-rw-elevated p-4"
      style={{ borderLeft: `3px solid ${cfg.hex}` }}
    >
      <p className="text-[11px] font-medium uppercase tracking-wide text-rw-dim">
        {cfg.label}
      </p>
      <p className="mt-1 text-2xl font-bold" style={{ color: cfg.hex }}>
        {value}
      </p>
    </div>
  );
}

/**
 * Run Compare — diff the current run's findings against a chosen baseline run.
 * Pick a baseline from the run list, then view NEW / RECURRING / FIXED columns
 * plus headline summary tiles.
 */
export function RunComparePage() {
  const { runId } = useParams<{ runId: string }>();
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [baseline, setBaseline] = useState<string>("");
  const [result, setResult] = useState<RunCompare | null>(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Candidate baselines: every run except the one we're comparing.
  const baselineOptions = useMemo(
    () => runs.filter((r) => r.run_id !== runId),
    [runs, runId],
  );

  useEffect(() => {
    setLoadingRuns(true);
    api.runs
      .list()
      .then(setRuns)
      .catch(() => setError("Could not load runs"))
      .finally(() => setLoadingRuns(false));
  }, []);

  useEffect(() => {
    if (!runId || !baseline) {
      setResult(null);
      return;
    }
    setComparing(true);
    setError(null);
    api.runs
      .compare(runId, baseline)
      .then(setResult)
      .catch(() => setError("Comparison failed"))
      .finally(() => setComparing(false));
  }, [runId, baseline]);

  const baselineLabel = (r: RunSummary) =>
    `${r.target || r.run_id.slice(0, 8)} · ${r.run_id.slice(0, 8)}`;

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Header */}
      <div className="mb-5">
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-rw-text">
          <GitCompareArrows size={22} className="text-rw-accent" />
          Run Compare
        </h1>
        <p className="mt-1 font-mono text-xs text-rw-dim">run {runId}</p>
      </div>

      {/* Baseline picker */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <label
          htmlFor="baseline-select"
          className="text-sm font-medium text-rw-muted"
        >
          Compare against baseline
        </label>
        <select
          id="baseline-select"
          value={baseline}
          onChange={(e) => setBaseline(e.target.value)}
          disabled={loadingRuns || baselineOptions.length === 0}
          className={cn(
            "min-w-[18rem] rounded-lg border border-rw-border bg-rw-input px-3 py-2 text-sm text-rw-text",
            "focus:border-rw-accent focus:outline-none disabled:opacity-50",
          )}
        >
          <option value="">
            {loadingRuns
              ? "Loading runs…"
              : baselineOptions.length === 0
                ? "No other runs available"
                : "Select a baseline run…"}
          </option>
          {baselineOptions.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {baselineLabel(r)}
            </option>
          ))}
        </select>
        {comparing && <Spinner size="sm" label="Comparing…" />}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Body */}
      {!baseline ? (
        <EmptyState
          icon={<GitCompareArrows size={32} />}
          title="Pick a baseline to compare"
          description="Choose a previous run above to see which findings are new, recurring, or fixed."
        />
      ) : result ? (
        <>
          {/* Summary tiles */}
          <div className="mb-5 grid grid-cols-3 gap-3">
            <SummaryTile kind="new" value={result.summary.new} />
            <SummaryTile kind="recurring" value={result.summary.recurring} />
            <SummaryTile kind="fixed" value={result.summary.fixed} />
          </div>

          {/* Three columns */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <DeltaColumn kind="new" findings={result.new} />
            <DeltaColumn kind="recurring" findings={result.recurring} />
            <DeltaColumn kind="fixed" findings={result.fixed} />
          </div>
        </>
      ) : (
        !comparing &&
        !error && (
          <div className="flex items-center gap-2 text-rw-muted">
            <Spinner /> <span className="text-sm">Loading comparison…</span>
          </div>
        )
      )}
    </div>
  );
}
