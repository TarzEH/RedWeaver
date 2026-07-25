import { useRef } from "react";
import type { TrendMetric } from "./metrics";

/**
 * Return the previous `TrendMetric` object whenever the new one is value-equal.
 *
 * The 5s poll hands back a fresh `runs` array on every tick, so any trend
 * derived from it is a brand-new object even when not a single number moved.
 * Recharts treats a new `data` array as a data change and replays its entry
 * animation — which is the "the dashboard keeps reloading itself" bug, just
 * relocated. Comparing by value and holding the old reference means an
 * unchanged chart is genuinely unchanged as far as React and recharts are
 * concerned, and it re-renders only when the figures really move.
 */
export function useStableTrend(next: TrendMetric): TrendMetric {
  const ref = useRef(next);
  const prev = ref.current;

  const unchanged =
    prev === next ||
    (prev.current === next.current &&
      prev.baseline === next.baseline &&
      prev.points.length === next.points.length &&
      prev.splitIndex === next.splitIndex &&
      prev.points.every((p, i) => p.ts === next.points[i].ts && p.value === next.points[i].value));

  if (!unchanged) ref.current = next;
  return ref.current;
}
