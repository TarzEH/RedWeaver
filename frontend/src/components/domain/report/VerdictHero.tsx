import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { severityHex, SEVERITY_ORDER } from "../../../config/theme";
import type { Finding, VulnerabilityReport } from "../../../types/api";
import { cn } from "../../../lib/cn";

interface VerdictHeroProps {
  report: VulnerabilityReport;
  className?: string;
}

/** Maps a (case-insensitive) overall risk rating to a display color + label. */
function ratingStyle(rating: string): { color: string; label: string; glow: string } {
  const r = (rating || "").trim().toLowerCase();
  if (r.startsWith("crit")) return { color: severityHex("critical"), label: "Critical", glow: "rgba(239,68,68,0.18)" };
  if (r.startsWith("high")) return { color: severityHex("high"), label: "High", glow: "rgba(249,115,22,0.16)" };
  if (r.startsWith("med")) return { color: severityHex("medium"), label: "Medium", glow: "rgba(234,179,8,0.14)" };
  if (r.startsWith("low")) return { color: severityHex("low"), label: "Low", glow: "rgba(59,130,246,0.14)" };
  if (r.startsWith("info")) return { color: severityHex("info"), label: "Informational", glow: "rgba(100,116,139,0.12)" };
  return { color: severityHex("info"), label: rating || "Unknown", glow: "rgba(100,116,139,0.12)" };
}

/** Pull severity counts from structured map(s) with a fallback to raw findings. */
function severityCounts(report: VulnerabilityReport): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const s of SEVERITY_ORDER) counts[s] = 0;
  const src = report.total_by_severity ?? report.findings_by_severity;
  if (src) {
    for (const [k, v] of Object.entries(src)) {
      const key = k.toLowerCase();
      if (key in counts) counts[key] = (counts[key] || 0) + (Number(v) || 0);
    }
    return counts;
  }
  for (const f of report.findings ?? ([] as Finding[])) {
    const key = (f.severity || "info").toLowerCase();
    if (key in counts) counts[key] += 1;
  }
  return counts;
}

export function VerdictHero({ report, className }: VerdictHeroProps) {
  const counts = useMemo(() => severityCounts(report), [report]);
  const total = useMemo(() => SEVERITY_ORDER.reduce((sum, s) => sum + (counts[s] || 0), 0), [counts]);
  const rating = ratingStyle(report.risk_rating);

  const donutData = useMemo(
    () => SEVERITY_ORDER.map((s) => ({ name: s, value: counts[s] || 0 })).filter((d) => d.value > 0),
    [counts],
  );

  return (
    <section
      className={cn(
        "rounded-2xl border border-rw-border bg-rw-elevated p-6 lg:p-8",
        "grid grid-cols-1 gap-8 lg:grid-cols-[1fr_auto]",
        className,
      )}
      aria-label="Overall risk verdict"
    >
      {/* Verdict word + tiles */}
      <div className="flex flex-col justify-between gap-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-rw-dim">Overall Risk Rating</p>
          <div className="mt-2 flex items-baseline gap-4">
            <span
              className="text-5xl font-extrabold leading-none tracking-tight lg:text-6xl"
              style={{ color: rating.color, textShadow: `0 0 28px ${rating.glow}` }}
            >
              {rating.label}
            </span>
            <span className="text-sm text-rw-muted">
              {total} {total === 1 ? "finding" : "findings"}
            </span>
          </div>
          <p className="mt-3 max-w-prose font-mono text-xs text-rw-dim">{report.target}</p>
        </div>

        {/* Severity count tiles — color + text label for accessibility */}
        <div className="grid grid-cols-5 gap-2">
          {SEVERITY_ORDER.map((sev) => {
            const c = counts[sev] || 0;
            const hex = severityHex(sev);
            return (
              <div
                key={sev}
                className={cn(
                  "rounded-lg border bg-rw-surface/40 px-2 py-2.5 text-center transition-colors",
                  c > 0 ? "border-rw-border" : "border-rw-border-subtle opacity-60",
                )}
                style={c > 0 ? { borderColor: `${hex}55` } : undefined}
              >
                <div className="text-xl font-bold tabular-nums" style={{ color: c > 0 ? hex : undefined }}>
                  {c}
                </div>
                <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-rw-dim">{sev}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Donut with total in the hole */}
      <div className="relative mx-auto h-44 w-44 shrink-0 lg:h-52 lg:w-52">
        {total > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="name"
                innerRadius="64%"
                outerRadius="92%"
                paddingAngle={2}
                stroke="none"
                isAnimationActive={false}
              >
                {donutData.map((d) => (
                  <Cell key={d.name} fill={severityHex(d.name)} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "#111827",
                  border: "1px solid #334155",
                  borderRadius: 8,
                  fontSize: 12,
                  textTransform: "capitalize",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full w-full items-center justify-center rounded-full border-2 border-dashed border-rw-border-subtle" />
        )}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold tabular-nums text-rw-text">{total}</span>
          <span className="text-[10px] uppercase tracking-widest text-rw-dim">findings</span>
        </div>
      </div>
    </section>
  );
}
