import { useId } from "react";
import { cn } from "../../../lib/cn";

interface SparklineProps {
  /** Chronological values, oldest → newest. 7–30 points reads well. */
  values: readonly number[];
  /** Sentence describing the shape for screen readers and print. */
  label: string;
  /** Index where the current window starts; a hairline marks the boundary. */
  splitIndex?: number;
  stroke?: string;
  className?: string;
}

const VIEW_W = 100;
const VIEW_H = 32;
/** Keeps the stroke off the top and bottom edges so peaks are not clipped. */
const PAD = 3;

/**
 * A bare trend line — no axes, no grid, no tooltip, no animation.
 *
 * This is deliberately hand-rolled SVG rather than a recharts chart: four of
 * these sit in the KPI row, where a full chart runtime per tile buys nothing.
 * Its job is shape only; the exact figures are already stated as text in the
 * card, so nothing here is hover-only — it survives print and a screen reader.
 */
export function Sparkline({ values, label, splitIndex, stroke = "#3b82f6", className }: SparklineProps) {
  const gradientId = useId();

  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const stepX = VIEW_W / (values.length - 1);

  // A flat series (including all-zero) has no meaningful vertical position, so
  // it rides the middle rather than collapsing onto the floor, where it would
  // be indistinguishable from the card's border.
  const y = (v: number) =>
    span === 0 ? VIEW_H / 2 : VIEW_H - PAD - ((v - min) / span) * (VIEW_H - PAD * 2);

  const coords = values.map((v, i) => [i * stepX, y(v)] as const);
  const line = coords.map(([x, yy], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${yy.toFixed(2)}`).join(" ");
  const area = `${line} L${VIEW_W},${VIEW_H} L0,${VIEW_H} Z`;

  const [lastX, lastY] = coords[coords.length - 1];
  const splitX = splitIndex != null && splitIndex > 0 && splitIndex < values.length
    ? splitIndex * stepX
    : null;

  return (
    <svg
      viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
      // The card widths vary, so the line stretches horizontally. Strokes are
      // pinned to device pixels with vector-effect so they never smear.
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
      className={cn("h-8 w-full overflow-visible", className)}
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>

      {splitX !== null && (
        // Where the baseline window ends and the current one begins — the
        // sparkline is otherwise a single undifferentiated 14-day run.
        <line
          x1={splitX}
          y1={0}
          x2={splitX}
          y2={VIEW_H}
          stroke="#334155"
          strokeWidth={1}
          strokeDasharray="2 2"
          vectorEffect="non-scaling-stroke"
        />
      )}

      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* A rect, not a circle: the non-uniform scale would squash a circle into
          an ellipse of unpredictable width. */}
      <rect
        x={lastX - 1.4}
        y={lastY - 1.4}
        width={2.8}
        height={2.8}
        fill={stroke}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
