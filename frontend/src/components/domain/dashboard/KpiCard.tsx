import type { LucideIcon } from "lucide-react";
import { Card } from "../../ui/Card";
import { Sparkline } from "./Sparkline";
import { DeltaIndicator } from "./DeltaIndicator";
import type { MetricDirection, TrendMetric } from "../../../features/dashboard/metrics";

interface KpiCardProps {
  label: string;
  /** Pre-formatted headline figure — the card never does arithmetic. */
  value: string;
  icon: LucideIcon;
  iconClass?: string;
  trend: TrendMetric;
  direction: MetricDirection;
  /** How the comparison is named to the reader, e.g. "previous 7d". */
  baselineLabel?: string;
  /** Renders the absolute delta when a percentage is not stateable. */
  formatAbsolute: (value: number) => string;
  sentimentWords?: { good: string; bad: string };
  /** Standing context under the sparkline, e.g. the all-time total. */
  footnote?: string;
  sparkStroke?: string;
}

/**
 * One statistic, with the three things that make it readable: what it measures,
 * how it compares to a named baseline, and where it has been.
 *
 * The value is rendered as plain text and never counts up. An odometer forces a
 * screen reader to announce every intermediate value, and the animation is
 * shown during exactly the moment the reader is trying to read the number.
 */
export function KpiCard({
  label,
  value,
  icon: Icon,
  iconClass = "text-rw-accent",
  trend,
  direction,
  baselineLabel = "previous 7d",
  formatAbsolute,
  sentimentWords,
  footnote,
  sparkStroke,
}: KpiCardProps) {
  const values = trend.points.map((p) => p.value);
  const peak = trend.points.reduce((a, b) => (b.value > a.value ? b : a), trend.points[0]);

  return (
    <Card className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <Icon size={16} className={iconClass} aria-hidden />
        <span className="text-xs font-medium text-rw-muted">{label}</span>
      </div>

      {/* tabular-nums so a value ticking 9 → 10 does not reflow the row. */}
      <div className="text-2xl font-bold tabular-nums leading-none text-rw-text">{value}</div>

      <DeltaIndicator
        absoluteDelta={trend.absoluteDelta}
        percentDelta={trend.percentDelta}
        direction={direction}
        baselineLabel={baselineLabel}
        formatAbsolute={formatAbsolute}
        sentimentWords={sentimentWords}
      />

      <Sparkline
        values={values}
        splitIndex={trend.splitIndex}
        stroke={sparkStroke}
        label={
          peak
            ? `${label}, daily over the last ${values.length} days. ` +
              `Current 7d total ${formatAbsolute(trend.current)}, ` +
              `baseline 7d total ${formatAbsolute(trend.baseline)}. ` +
              `Busiest day ${peak.label} at ${formatAbsolute(peak.value)}.`
            : `${label} trend`
        }
      />

      {footnote && <p className="text-[11px] tabular-nums text-rw-dim">{footnote}</p>}
    </Card>
  );
}
