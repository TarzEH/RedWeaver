import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { severityHex, SEVERITY_ORDER } from "../../../config/theme";
import type { Severity } from "../../../types/api";
import { cn } from "../../../lib/cn";

interface SeverityBarProps {
  /** Ordinal severity → count map (any casing accepted). */
  counts: Record<string, number>;
  className?: string;
}

interface Row {
  severity: Severity;
  label: string;
  count: number;
}

const LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

/** Renders the count at the end of each bar. recharts LabelList content. */
function renderCountLabel(props: {
  x?: string | number;
  y?: string | number;
  width?: string | number;
  height?: string | number;
  value?: string | number;
}) {
  const x = Number(props.x ?? 0);
  const y = Number(props.y ?? 0);
  const width = Number(props.width ?? 0);
  const height = Number(props.height ?? 0);
  const value = Number(props.value ?? 0);
  if (value <= 0) return null;
  const inside = width > 28;
  return (
    <text
      x={inside ? x + width - 8 : x + width + 6}
      y={y + height / 2}
      textAnchor={inside ? "end" : "start"}
      dominantBaseline="central"
      fontSize={12}
      fontWeight={700}
      fill={inside ? "#0b0f14" : "#f1f5f9"}
    >
      {value}
    </text>
  );
}

export function SeverityBar({ counts, className }: SeverityBarProps) {
  const rows = useMemo<Row[]>(
    () =>
      SEVERITY_ORDER.map((s) => ({
        severity: s,
        label: LABELS[s],
        count: Number(counts[s] ?? counts[s.toLowerCase()] ?? 0) || 0,
      })),
    [counts],
  );

  const total = rows.reduce((sum, r) => sum + r.count, 0);

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm font-semibold text-rw-text">Findings by Severity</span>
        <span className="ml-auto text-xs text-rw-dim">{total} total</span>
      </div>

      {/* Sorted Critical→Info bar (recharts). Color + text label for accessibility. */}
      <ResponsiveContainer width="100%" height={Math.max(160, rows.length * 38)}>
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 36, bottom: 4, left: 8 }}
        >
          <XAxis type="number" hide domain={[0, Math.max(1, total)]} />
          <YAxis
            type="category"
            dataKey="label"
            width={68}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#94a3b8", fontSize: 12 }}
          />
          <Tooltip
            cursor={{ fill: "rgba(148,163,184,0.08)" }}
            contentStyle={{
              background: "#111827",
              border: "1px solid #334155",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number | string) => [value, "Findings"]}
          />
          <Bar dataKey="count" radius={[4, 4, 4, 4]} barSize={20} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.severity} fill={severityHex(r.severity)} />
            ))}
            <LabelList dataKey="count" content={renderCountLabel} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Accessible legend — describes color encoding in text */}
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        {rows.map((r) => (
          <li key={r.severity} className="flex items-center gap-1.5 text-[11px] text-rw-dim">
            <span
              aria-hidden
              className="inline-block h-2.5 w-2.5 rounded-sm"
              style={{ background: severityHex(r.severity) }}
            />
            <span>
              {r.label}: <span className="font-semibold text-rw-muted tabular-nums">{r.count}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
