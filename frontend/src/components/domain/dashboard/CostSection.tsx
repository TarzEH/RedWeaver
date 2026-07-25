import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DollarSign } from "lucide-react";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { StatGrid } from "../../ui/StatGrid";
import { FreshnessLabel } from "./FreshnessLabel";
import { DeltaIndicator } from "./DeltaIndicator";
import { percentile, type TrendMetric } from "../../../features/dashboard/metrics";
import { formatTokens, formatUsd, sumUsd, toNumber } from "../../../lib/money";
import { cn } from "../../../lib/cn";
import type { RunSummary } from "../../../types/api";

interface CostSectionProps {
  runs: readonly RunSummary[];
  /** Daily spend series + 7d-over-7d delta, built by the page. */
  spendTrend: TrendMetric;
  updatedAt: number | null;
  paused: boolean;
  onOpenRun: (runId: string) => void;
}

/** How many of the priciest runs to name. */
const TOP_N = 8;

/**
 * Axis ticks — short, but never ambiguous.
 *
 * Rounding to whole dollars collapsed a $3.26/$2.71 axis into two ticks both
 * reading "$3", which makes the scale unreadable. Daily spend lives in the
 * single digits, so cents are kept until the numbers are large enough not to
 * need them.
 */
function axisUsd(value: number): string {
  if (value === 0) return "$0";
  if (value < 10) return `$${value.toFixed(2)}`;
  return `$${Math.round(value)}`;
}

interface CostedRun {
  run: RunSummary;
  cost: number;
  budget: number | null;
}

/**
 * What the hunts actually cost.
 *
 * Deliberately reports p50 and p95 and **no mean**. Agent-run spend is a long
 * tail — one published benchmark of 1,127 runs put p95/p50 near 18× — so an
 * average sits above almost every run while still hiding the handful that
 * consume the budget. The named-and-sorted list of the priciest runs is the
 * part that actually answers "where did the money go".
 *
 * Every figure here arrives from DRF as a *string* (`DecimalField`), so it is
 * coerced through `lib/money` before any arithmetic; `+` on the raw values
 * would silently concatenate.
 */
export function CostSection({ runs, spendTrend, updatedAt, paused, onOpenRun }: CostSectionProps) {
  const { costed, total, p50, p95, tailRatio, topRuns, totalTokens } = useMemo(() => {
    const withCost: CostedRun[] = [];
    for (const run of runs) {
      const cost = toNumber(run.cost_usd);
      if (cost === null) continue;
      withCost.push({ run, cost, budget: toNumber(run.budget_usd) });
    }

    const amounts = withCost.map((c) => c.cost);
    const median = percentile(amounts, 50);
    const upper = percentile(amounts, 95);

    return {
      costed: withCost,
      total: sumUsd(runs.map((r) => r.cost_usd)),
      p50: median,
      p95: upper,
      tailRatio: median !== null && upper !== null && median > 0 ? upper / median : null,
      topRuns: [...withCost].sort((a, b) => b.cost - a.cost).slice(0, TOP_N),
      totalTokens: runs.reduce((sum, r) => sum + (r.total_tokens ?? 0), 0),
    };
  }, [runs]);

  const header = (
    <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
      <h2 className="text-sm font-medium uppercase tracking-wider text-rw-muted">Spend</h2>
      <FreshnessLabel at={updatedAt} paused={paused} className="ml-auto" />
    </div>
  );

  if (costed.length === 0) {
    return (
      <section className="mb-8">
        {header}
        <Card>
          <EmptyState
            icon={<DollarSign size={32} />}
            title="No spend recorded yet"
            description="Cost appears once a hunt has run and reported its token usage."
          />
        </Card>
      </section>
    );
  }

  const peak = spendTrend.points.reduce((a, b) => (b.value > a.value ? b : a), spendTrend.points[0]);
  const maxTopCost = topRuns[0]?.cost ?? 0;

  return (
    <section className="mb-8">
      {header}

      {/* Headline totals + the two order statistics that survive a long tail. */}
      {/* StatGrid keys off this row's own width rather than the viewport, so
          the tiles stay readable if the section is ever rendered narrow. The
          Spend Over Time chart deliberately stays outside it: container-type
          containment resolves a percentage height against zero. */}
      <StatGrid className="mb-4">
        <Card className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-rw-muted">Total spend</span>
          <span className="text-2xl font-bold tabular-nums leading-none text-rw-text">
            {formatUsd(total)}
          </span>
          <DeltaIndicator
            absoluteDelta={spendTrend.absoluteDelta}
            percentDelta={spendTrend.percentDelta}
            direction="up-bad"
            baselineLabel="previous 7d"
            formatAbsolute={(v) => formatUsd(v)}
            sentimentWords={{ good: "cheaper", bad: "pricier" }}
          />
          <span className="text-[11px] tabular-nums text-rw-dim">
            {costed.length} priced run{costed.length === 1 ? "" : "s"} ·{" "}
            {formatTokens(totalTokens)} tokens
          </span>
        </Card>

        <Card className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-rw-muted">Median run (p50)</span>
          <span className="text-2xl font-bold tabular-nums leading-none text-rw-text">
            {p50 === null ? "—" : formatUsd(p50)}
          </span>
          <span className="text-[11px] text-rw-dim">Half of all runs cost less than this.</span>
        </Card>

        <Card className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-rw-muted">Expensive run (p95)</span>
          <span className="text-2xl font-bold tabular-nums leading-none text-rw-text">
            {p95 === null ? "—" : formatUsd(p95)}
          </span>
          <span className="text-[11px] tabular-nums text-rw-dim">
            {tailRatio !== null
              ? `${tailRatio.toFixed(tailRatio < 10 ? 1 : 0)}× the median — the tail, not the typical run.`
              : "1 in 20 runs costs at least this much."}
          </span>
        </Card>

        <Card className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-rw-muted">Why no average</span>
          <p className="text-[11px] leading-relaxed text-rw-dim">
            Run cost is long-tailed: a few runs dominate the total. A mean would sit above
            almost every run and still hide the ones doing the spending — so this panel
            reports <span className="text-rw-muted">p50</span> and{" "}
            <span className="text-rw-muted">p95</span>, and names the outliers on the right.
          </p>
        </Card>
      </StatGrid>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* Spend over time — same treatment as Findings Over Time. */}
        <Card className="lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-rw-text">Spend Over Time</span>
            <span className="text-xs tabular-nums text-rw-dim">
              last {spendTrend.points.length} days
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            {/* isAnimationActive is left at its default: forcing it true would
                override a viewer's prefers-reduced-motion setting. */}
            <AreaChart data={spendTrend.points} margin={{ top: 4, right: 8, left: -6, bottom: 0 }}>
              <defs>
                <linearGradient id="rwSpendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.04} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" />
              <YAxis
                tick={{ fill: "#8b9cb3", fontSize: 11 }}
                stroke="#334155"
                width={52}
                tickFormatter={axisUsd}
              />
              <Tooltip
                contentStyle={{
                  background: "#111827",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value) => [formatUsd(value as number), "Spend"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                name="Spend"
                stroke="#3b82f6"
                strokeWidth={1.5}
                fill="url(#rwSpendFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
          {/* The chart's numbers are hover-only, which is no good in print or
              with a screen reader — state the shape in text as well. */}
          <p className="mt-2 text-[11px] text-rw-dim">
            <span className="sr-only">Daily spend. </span>
            {formatUsd(spendTrend.current)} in the last 7d vs {formatUsd(spendTrend.baseline)} in the
            7d before.{peak && peak.value > 0 ? ` Heaviest day ${peak.label} at ${formatUsd(peak.value)}.` : ""}
          </p>
        </Card>

        {/* The list that an average would have hidden. */}
        <Card className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium text-rw-text">Most Expensive Hunts</span>
            <span className="text-xs tabular-nums text-rw-dim">top {topRuns.length}</span>
          </div>
          <ol className="space-y-1">
            {topRuns.map(({ run, cost, budget }, i) => {
              const overBudget = budget !== null && budget > 0 && cost >= budget;
              const share = total > 0 ? (cost / total) * 100 : 0;
              return (
                <li key={run.run_id}>
                  <button
                    type="button"
                    onClick={() => onOpenRun(run.run_id)}
                    aria-label={`Open hunt for ${run.target}, cost ${formatUsd(cost)}`}
                    className={cn(
                      "group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left",
                      "transition-colors hover:bg-rw-surface",
                      "focus-visible:ring-2 focus-visible:ring-rw-accent",
                    )}
                  >
                    <span className="w-4 shrink-0 text-right text-[11px] tabular-nums text-rw-dim">
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-mono text-xs text-rw-text">
                        {run.target}
                      </span>
                      <span className="mt-1 flex items-center gap-1.5">
                        <span
                          aria-hidden
                          className="h-1 flex-1 overflow-hidden rounded-full bg-rw-surface"
                        >
                          <span
                            className="block h-full rounded-full bg-rw-accent"
                            style={{ width: `${maxTopCost > 0 ? (cost / maxTopCost) * 100 : 0}%` }}
                          />
                        </span>
                        <span className="shrink-0 text-[10px] tabular-nums text-rw-dim">
                          {share.toFixed(0)}% of total
                        </span>
                      </span>
                    </span>
                    <span className="shrink-0 text-right">
                      <span className="block text-xs font-semibold tabular-nums text-rw-text">
                        {formatUsd(cost)}
                      </span>
                      <span className="block text-[10px] tabular-nums text-rw-dim">
                        {run.total_tokens != null ? `${formatTokens(run.total_tokens)} tok` : "—"}
                      </span>
                      {/* Words, not just a red tint: this run stopped early. */}
                      {overBudget && (
                        <span className="block text-[10px] text-red-400">ceiling reached</span>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </Card>
      </div>
    </section>
  );
}
