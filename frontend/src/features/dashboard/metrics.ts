/**
 * Dashboard metric maths — windows, daily buckets, percentiles.
 *
 * Every number on the dashboard is shown against a *named* baseline, because a
 * bare count ("7 failed") forces the reader to supply the comparison from
 * memory. The baseline used throughout is the **previous 7 days**: the trailing
 * 7 calendar days versus the 7 before them, with a 14-day daily series so the
 * sparkline shows the baseline period and the current period side by side.
 *
 * Pure functions only — no React, no formatting. Rendering lives in
 * `components/domain/dashboard/`.
 */

import { percentChange } from "../../lib/money";

export const DAY_MS = 86_400_000;
/** Length of the comparison window, in days. Also the baseline's length. */
export const WINDOW_DAYS = 7;
/** Points in the sparkline: the current window plus the baseline window. */
export const SERIES_DAYS = WINDOW_DAYS * 2;

/**
 * Which way is "good" for this metric.
 *
 * There is no universal answer — `Failed ↑` is bad news and `Completed ↑` is
 * good news, and a dashboard that draws both in the same colour (or, worse,
 * assumes up is always green) actively misleads. Each metric declares its own
 * semantic and the UI renders a *word* for it, never colour alone.
 */
export type MetricDirection = "up-good" | "up-bad" | "neutral";

export type Sentiment = "good" | "bad" | "neutral";

/** Resolve a signed delta plus a metric's semantic into a judgement. */
export function sentimentFor(delta: number, direction: MetricDirection): Sentiment {
  if (direction === "neutral" || delta === 0) return "neutral";
  const up = delta > 0;
  if (direction === "up-good") return up ? "good" : "bad";
  return up ? "bad" : "good";
}

export interface DailyPoint {
  /** Local midnight of the bucket. */
  ts: number;
  /** Short axis label, e.g. "Jul 12". */
  label: string;
  value: number;
}

export interface TrendMetric {
  /** Total across the trailing `WINDOW_DAYS`. */
  current: number;
  /** Total across the `WINDOW_DAYS` before that — the named baseline. */
  baseline: number;
  absoluteDelta: number;
  /** Null when the baseline is zero: a percentage off zero is not a fact. */
  percentDelta: number | null;
  /** `SERIES_DAYS` buckets, oldest → newest. */
  points: DailyPoint[];
  /** Index in `points` where the current window starts (baseline is before it). */
  splitIndex: number;
}

/** Local midnight for a timestamp. */
function startOfDay(ts: number): number {
  const d = new Date(ts);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

function dayLabel(ts: number): string {
  return new Date(ts).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Bucket `items` into daily totals and derive the window-over-window delta.
 *
 * `at` returns the item's ISO timestamp (items with an unparseable or missing
 * one are skipped rather than silently landing in "today"), `value` returns the
 * quantity to sum — 1 for a count, the dollar figure for spend.
 */
export function buildDailyTrend<T>(
  items: readonly T[],
  at: (item: T) => string | null | undefined,
  value: (item: T) => number,
  now: number,
  days: number = SERIES_DAYS,
  windowDays: number = WINDOW_DAYS,
): TrendMetric {
  const today = startOfDay(now);

  // Walk back a day at a time with Date arithmetic rather than subtracting
  // 86_400_000 repeatedly, so a DST transition does not shift the buckets.
  const points: DailyPoint[] = [];
  for (let back = days - 1; back >= 0; back--) {
    const d = new Date(today);
    d.setDate(d.getDate() - back);
    const ts = d.getTime();
    points.push({ ts, label: dayLabel(ts), value: 0 });
  }
  const indexByTs = new Map(points.map((p, i) => [p.ts, i]));

  for (const item of items) {
    const raw = at(item);
    if (!raw) continue;
    const parsed = new Date(raw).getTime();
    if (!Number.isFinite(parsed)) continue;
    const idx = indexByTs.get(startOfDay(parsed));
    if (idx === undefined) continue;
    const v = value(item);
    if (Number.isFinite(v)) points[idx].value += v;
  }

  const splitIndex = Math.max(0, days - windowDays);
  const sum = (from: number, to: number) =>
    points.slice(from, to).reduce((total, p) => total + p.value, 0);

  const current = sum(splitIndex, days);
  const baseline = sum(Math.max(0, splitIndex - windowDays), splitIndex);

  return {
    current,
    baseline,
    absoluteDelta: current - baseline,
    percentDelta: percentChange(current, baseline),
    points,
    splitIndex,
  };
}

/**
 * Linear-interpolated percentile of `values`.
 *
 * Agent-run cost is a long tail — a benchmark of 1,127 runs put p95/p50 at
 * roughly 18×. A mean over that distribution describes no run that actually
 * happened, so the dashboard reports p50 and p95 and never an average.
 */
export function percentile(values: readonly number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  if (sorted.length === 1) return sorted[0];
  const rank = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(rank);
  const hi = Math.ceil(rank);
  if (lo === hi) return sorted[lo];
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (rank - lo);
}

/** "4s ago" / "12m ago" — second-granular, unlike `formatRelativeDate`. */
export function formatAge(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return "just now";
  const s = Math.floor(ms / 1000);
  if (s < 1) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}
