import { cn } from "../../../lib/cn";
import { sentimentFor, type MetricDirection, type Sentiment } from "../../../features/dashboard/metrics";

interface DeltaIndicatorProps {
  /** Signed change against the baseline, in the metric's own units. */
  absoluteDelta: number;
  /** Signed percentage change, or null when the baseline was zero. */
  percentDelta: number | null;
  /** Which way is "good" for this particular metric. */
  direction: MetricDirection;
  /** Names the comparison, e.g. "previous 7d". Never omit it. */
  baselineLabel: string;
  /** Renders the absolute fallback when a percentage cannot be stated. */
  formatAbsolute: (value: number) => string;
  /** Per-metric wording for the judgement, e.g. "cheaper"/"pricier". */
  sentimentWords?: { good: string; bad: string };
  className?: string;
}

/** Colour is reinforcement only — the word next to it carries the meaning. */
const sentimentClass: Record<Sentiment, string> = {
  good: "text-emerald-400",
  bad: "text-red-400",
  neutral: "text-rw-dim",
};

export function DeltaIndicator({
  absoluteDelta,
  percentDelta,
  direction,
  baselineLabel,
  formatAbsolute,
  sentimentWords = { good: "better", bad: "worse" },
  className,
}: DeltaIndicatorProps) {
  const sentiment = sentimentFor(absoluteDelta, direction);
  const flat = absoluteDelta === 0;
  const up = absoluteDelta > 0;

  const arrow = flat ? "→" : up ? "↑" : "↓";
  const spokenArrow = flat ? "unchanged" : up ? "up" : "down";

  // A percentage against a zero baseline is either Infinity or an invented
  // 100% — both lie. Fall back to the absolute change and say so on hover.
  const magnitude = flat
    ? "no change"
    : percentDelta !== null
      ? `${Math.abs(percentDelta).toFixed(percentDelta !== 0 && Math.abs(percentDelta) < 10 ? 1 : 0)}%`
      : formatAbsolute(Math.abs(absoluteDelta));

  const judgement =
    sentiment === "neutral" ? null : sentiment === "good" ? sentimentWords.good : sentimentWords.bad;

  return (
    <p className={cn("flex flex-wrap items-baseline gap-x-1.5 text-xs", className)}>
      <span className={cn("font-medium tabular-nums", sentimentClass[sentiment])}>
        <span aria-hidden>{arrow} </span>
        <span className="sr-only">{spokenArrow} </span>
        {magnitude}
      </span>
      <span
        className="text-rw-dim"
        title={
          percentDelta === null && !flat
            ? `Nothing was recorded in the ${baselineLabel}, so a percentage would be meaningless — this is the absolute change.`
            : undefined
        }
      >
        vs {baselineLabel}
      </span>
      {judgement && (
        // Spelled out because ~8% of men cannot separate the red from the
        // green, and because an arrow alone does not say whether up is good.
        <span className={cn("font-medium", sentimentClass[sentiment])}>· {judgement}</span>
      )}
    </p>
  );
}
