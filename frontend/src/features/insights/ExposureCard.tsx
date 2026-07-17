import { useMemo } from "react";
import { ShieldAlert } from "lucide-react";
import type { Finding, Severity } from "../../types/api";
import { SEVERITY_ORDER, severityHex } from "../../config/theme";
import { cn } from "../../lib/cn";

/** Per-severity contribution to the composite exposure score. */
const SEVERITY_WEIGHT: Record<Severity, number> = {
  critical: 10,
  high: 7,
  medium: 4,
  low: 2,
  info: 0.5,
};

interface Verdict {
  label: string;
  /** hex used for the ring + the big number */
  color: string;
  /** short, human verdict sentence */
  blurb: string;
}

function verdictFor(score: number): Verdict {
  if (score >= 75)
    return {
      label: "Critical exposure",
      color: severityHex("critical"),
      blurb: "Severe, actively-dangerous weaknesses — remediate immediately.",
    };
  if (score >= 50)
    return {
      label: "High exposure",
      color: severityHex("high"),
      blurb: "Significant attack surface — prioritize fixes this cycle.",
    };
  if (score >= 25)
    return {
      label: "Moderate exposure",
      color: severityHex("medium"),
      blurb: "Notable issues present — schedule remediation soon.",
    };
  if (score > 0)
    return {
      label: "Low exposure",
      color: severityHex("low"),
      blurb: "Minor findings only — monitor and harden opportunistically.",
    };
  return {
    label: "No exposure",
    color: severityHex("info"),
    blurb: "No findings recorded for this scope.",
  };
}

export interface ExposureCardProps {
  findings: Finding[];
  /** Optional context line (e.g. session id, host count). */
  subtitle?: string;
  className?: string;
}

/**
 * Composite "Exposure Score" (0–100) for a set of findings.
 *
 * Weights each finding by severity, then normalizes against a saturation
 * ceiling so a handful of criticals already reads as a high score (rather
 * than requiring an unrealistic volume of findings to move the needle).
 */
export function ExposureCard({ findings, subtitle, className }: ExposureCardProps) {
  const { score, counts, total } = useMemo(() => {
    const counts: Record<Severity, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      info: 0,
    };
    let weighted = 0;
    for (const f of findings) {
      const sev = (SEVERITY_ORDER.includes(f.severity) ? f.severity : "info") as Severity;
      counts[sev] += 1;
      weighted += SEVERITY_WEIGHT[sev];
    }
    // Saturation ceiling: ~3 criticals worth of weight maps to a full bar.
    const CEILING = 30;
    const normalized = Math.min(100, Math.round((weighted / CEILING) * 100));
    return { score: normalized, counts, total: findings.length };
  }, [findings]);

  const verdict = verdictFor(score);

  // Conic ring driven by the score; track stays a muted border tone.
  const ringStyle: React.CSSProperties = {
    background: `conic-gradient(${verdict.color} ${score * 3.6}deg, rgba(51,65,85,0.5) 0deg)`,
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-5 rounded-xl border border-rw-border bg-rw-elevated p-6 sm:flex-row sm:items-center",
        className,
      )}
    >
      {/* Score ring */}
      <div className="flex items-center gap-5">
        <div
          className="relative grid h-28 w-28 shrink-0 place-items-center rounded-full"
          style={ringStyle}
          role="img"
          aria-label={`Exposure score ${score} out of 100, ${verdict.label}`}
        >
          <div className="grid h-[5.5rem] w-[5.5rem] place-items-center rounded-full bg-rw-elevated">
            <span
              className="text-3xl font-bold leading-none"
              style={{ color: verdict.color }}
            >
              {score}
            </span>
            <span className="mt-0.5 text-[10px] font-medium uppercase tracking-wide text-rw-dim">
              / 100
            </span>
          </div>
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldAlert size={16} style={{ color: verdict.color }} />
            <h2 className="text-base font-semibold text-rw-text">Exposure Score</h2>
          </div>
          <p
            className="mt-1 text-sm font-semibold"
            style={{ color: verdict.color }}
          >
            {verdict.label}
          </p>
          <p className="mt-0.5 max-w-md text-xs text-rw-dim">{verdict.blurb}</p>
          {subtitle && <p className="mt-1 text-[11px] text-rw-dim">{subtitle}</p>}
        </div>
      </div>

      {/* Severity breakdown */}
      <div className="flex-1 sm:border-l sm:border-rw-border sm:pl-6">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-rw-dim">
          {total} finding{total === 1 ? "" : "s"} by severity
        </p>
        <div className="flex flex-wrap gap-2">
          {SEVERITY_ORDER.map((sev) => (
            <div
              key={sev}
              className="flex items-center gap-1.5 rounded-md border border-rw-border bg-rw-surface px-2.5 py-1"
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: severityHex(sev) }}
                aria-hidden
              />
              <span className="text-[11px] font-medium capitalize text-rw-muted">
                {sev}
              </span>
              <span className="font-mono text-xs font-semibold text-rw-text">
                {counts[sev]}
              </span>
            </div>
          ))}
        </div>

        {/* Linear bar mirroring the ring for at-a-glance scanning */}
        <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-rw-surface">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${score}%`, backgroundColor: verdict.color }}
          />
        </div>
      </div>
    </div>
  );
}
