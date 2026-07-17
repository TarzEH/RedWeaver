import { useMemo } from "react";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Cell,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { severityHex } from "../../../config/theme";
import type { Finding } from "../../../types/api";
import { cn } from "../../../lib/cn";

interface CvssEpssScatterProps {
  findings: Finding[];
  className?: string;
}

interface Point {
  epss: number;
  cvss: number;
  severity: string;
  title: string;
}

/** "Fix now" quadrant thresholds. */
const EPSS_THRESHOLD = 0.5;
const CVSS_THRESHOLD = 7;

function TooltipContent({ active, payload }: {
  active?: boolean;
  payload?: { payload: Point }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-rw-border bg-rw-elevated px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 max-w-[220px] truncate font-semibold text-rw-text">{p.title}</div>
      <div className="flex items-center gap-3 text-rw-muted">
        <span>CVSS {p.cvss.toFixed(1)}</span>
        <span>EPSS {(p.epss * 100).toFixed(1)}%</span>
        <span className="capitalize" style={{ color: severityHex(p.severity) }}>
          {p.severity}
        </span>
      </div>
    </div>
  );
}

export function CvssEpssScatter({ findings, className }: CvssEpssScatterProps) {
  const points = useMemo<Point[]>(() => {
    return (findings ?? [])
      .map((f) => {
        const cvss = f.cvss_score;
        const epss = f.epss_score;
        if (cvss == null || epss == null) return null;
        if (!Number.isFinite(cvss) || !Number.isFinite(epss)) return null;
        return {
          epss: Math.min(1, Math.max(0, epss)),
          cvss: Math.min(10, Math.max(0, cvss)),
          severity: (f.severity || "info").toLowerCase(),
          title: f.title,
        } satisfies Point;
      })
      .filter((p): p is Point => p !== null);
  }, [findings]);

  const fixNowCount = points.filter((p) => p.epss >= EPSS_THRESHOLD && p.cvss >= CVSS_THRESHOLD).length;

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm font-semibold text-rw-text">Risk Prioritization</span>
        <span className="text-xs text-rw-dim">CVSS severity vs EPSS exploit likelihood</span>
        {fixNowCount > 0 && (
          <span
            className="ml-auto rounded-md border px-2 py-0.5 text-[11px] font-semibold"
            style={{
              color: severityHex("critical"),
              borderColor: `${severityHex("critical")}55`,
              background: `${severityHex("critical")}14`,
            }}
          >
            {fixNowCount} in fix-now zone
          </span>
        )}
      </div>

      {points.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center rounded-lg border border-dashed border-rw-border-subtle text-xs text-rw-dim">
          No findings with both CVSS and EPSS scores.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart margin={{ top: 12, right: 20, bottom: 28, left: 4 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
            {/* Shaded upper-right "fix now" quadrant */}
            <ReferenceArea
              x1={EPSS_THRESHOLD}
              x2={1}
              y1={CVSS_THRESHOLD}
              y2={10}
              fill={severityHex("critical")}
              fillOpacity={0.1}
              stroke={severityHex("critical")}
              strokeOpacity={0.35}
              strokeDasharray="4 4"
              label={{
                value: "FIX NOW",
                position: "insideTopRight",
                fill: severityHex("critical"),
                fontSize: 10,
                fontWeight: 700,
              }}
            />
            <ReferenceLine x={EPSS_THRESHOLD} stroke="#334155" strokeDasharray="2 4" />
            <ReferenceLine y={CVSS_THRESHOLD} stroke="#334155" strokeDasharray="2 4" />
            <XAxis
              type="number"
              dataKey="epss"
              name="EPSS"
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              stroke="#334155"
              label={{ value: "EPSS (exploit likelihood)", position: "insideBottom", offset: -16, fill: "#8b9cb3", fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="cvss"
              name="CVSS"
              domain={[0, 10]}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              stroke="#334155"
              label={{ value: "CVSS", angle: -90, position: "insideLeft", fill: "#8b9cb3", fontSize: 11 }}
            />
            <ZAxis range={[60, 60]} />
            <Tooltip content={<TooltipContent />} cursor={{ strokeDasharray: "3 3", stroke: "#475569" }} />
            <Scatter data={points} isAnimationActive={false}>
              {points.map((p, i) => (
                <Cell key={i} fill={severityHex(p.severity)} fillOpacity={0.85} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
