import { useEffect, useMemo, useState } from "react";
import { TrendingUp, TrendingDown, Minus, Activity } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../../services/api";
import type { PostureSeries } from "../../services/api";
import { severityHex, SEVERITY_ORDER } from "../../config/theme";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/EmptyState";
import { Spinner } from "../ui/Spinner";
import { cn } from "../../lib/cn";

interface Props {
  sessionId: string;
  className?: string;
}

const TOOLTIP_STYLE = {
  background: "#111827",
  border: "1px solid #334155",
  borderRadius: 8,
  fontSize: 12,
} as const;

function shortDate(value: string): string {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value.slice(0, 10);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/**
 * Posture trend for a session: exposure score over time plus a stacked area of
 * findings broken out by severity. Shows the latest exposure with its delta vs.
 * the first data point. Renders an empty state when fewer than two points are
 * available (a single point is not a trend).
 */
export function PostureTrend({ sessionId, className }: Props) {
  const [series, setSeries] = useState<PostureSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.insights
      .posture(sessionId)
      .then((s) => {
        if (!cancelled) setSeries(s);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const points = series?.points ?? [];

  const chartData = useMemo(
    () =>
      points.map((p) => {
        const row: Record<string, number | string> = {
          date: shortDate(p.date),
          exposure: p.exposure ?? 0,
        };
        for (const sev of SEVERITY_ORDER) row[sev] = p.by_severity?.[sev] ?? 0;
        return row;
      }),
    [points],
  );

  const summary = useMemo(() => {
    if (points.length < 1) return null;
    const first = points[0].exposure ?? 0;
    const last = points[points.length - 1].exposure ?? 0;
    return { latest: last, delta: last - first };
  }, [points]);

  if (loading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Spinner size="md" label="Loading posture trend…" />
      </div>
    );
  }

  if (error || points.length < 2) {
    return (
      <EmptyState
        icon={<Activity size={32} />}
        title="Not enough history yet"
        description="Posture trends appear once this session has at least two completed hunts to compare over time."
      />
    );
  }

  const delta = summary?.delta ?? 0;
  const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  // Exposure is a risk score: rising exposure is bad (red), falling is good.
  const deltaColor =
    delta > 0 ? "text-red-400" : delta < 0 ? "text-emerald-400" : "text-rw-dim";

  return (
    <div className={cn("grid grid-cols-1 gap-4 lg:grid-cols-2", className)}>
      {/* Exposure over time */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-rw-text">Exposure Over Time</span>
          {summary && (
            <span className="flex items-center gap-3">
              <span className="font-mono text-lg font-bold text-rw-text">
                {summary.latest.toFixed(1)}
              </span>
              <span className={cn("flex items-center gap-1 text-xs font-semibold", deltaColor)}>
                <DeltaIcon size={13} />
                {delta > 0 ? "+" : ""}
                {delta.toFixed(1)}
              </span>
            </span>
          )}
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <defs>
              <linearGradient id="posture-exposure" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" />
            <YAxis tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" width={36} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Area
              type="monotone"
              dataKey="exposure"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#posture-exposure)"
            />
            <Line type="monotone" dataKey="exposure" stroke="#60a5fa" strokeWidth={0} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Card>

      {/* Findings by severity, stacked */}
      <Card>
        <span className="mb-3 block text-sm font-medium text-rw-text">
          Findings by Severity
        </span>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="date" tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" />
            <YAxis tick={{ fill: "#8b9cb3", fontSize: 11 }} stroke="#334155" width={36} allowDecimals={false} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
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
        <div className="mt-2 flex flex-wrap gap-3">
          {SEVERITY_ORDER.map((sev) => (
            <span key={sev} className="flex items-center gap-1.5 text-[10px] text-rw-dim">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: severityHex(sev) }}
                aria-hidden
              />
              <span className="capitalize">{sev}</span>
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
}
