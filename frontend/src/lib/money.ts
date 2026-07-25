/**
 * Cost formatting, shared by every surface that shows spend.
 *
 * DRF serializes `DecimalField` as a *string* ("0.7589"), so anything doing
 * arithmetic on `cost_usd` straight off the wire silently concatenates instead
 * of adding. Everything here coerces first.
 */

/** Coerce a DRF decimal (string | number | null) to a number; null-ish → null. */
export function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Format USD with enough precision to be non-zero.
 *
 * Agent runs routinely land in the cents, where two decimals would render a
 * real $0.0431 as "$0.00" — so sub-dollar amounts keep four.
 */
export function formatUsd(value: string | number | null | undefined): string {
  const n = toNumber(value);
  if (n === null) return "—";
  return n < 1 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
}

/** Compact token counts: 1,240 → "1.2k", 918,004 → "918k". */
export function formatTokens(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value < 1000) return String(value);
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`;
  return `${(value / 1_000_000).toFixed(1)}M`;
}

/** Sum a list of DRF decimals, skipping anything unparseable. */
export function sumUsd(values: Array<string | number | null | undefined>): number {
  return values.reduce<number>((total, v) => total + (toNumber(v) ?? 0), 0);
}

/**
 * Percentage-change against a baseline, or null when it cannot be stated.
 *
 * A baseline of zero has no meaningful percentage change — returning Infinity
 * or 100% there would invent a number, so callers get null and should render
 * the absolute value instead.
 */
export function percentChange(current: number, baseline: number): number | null {
  if (!Number.isFinite(current) || !Number.isFinite(baseline) || baseline === 0) return null;
  return ((current - baseline) / Math.abs(baseline)) * 100;
}
