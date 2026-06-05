import { useMemo } from "react";
import type { MitreTechnique } from "../../../types/api";
import { cn } from "../../../lib/cn";

interface MitreHeatmapProps {
  techniques?: MitreTechnique[];
  className?: string;
}

/** Blend the accent hue toward full opacity as count approaches the max. */
function cellShade(count: number, max: number): { bg: string; border: string; text: string } {
  if (count <= 0 || max <= 0) {
    return { bg: "rgba(30,41,59,0.4)", border: "rgba(51,65,85,0.6)", text: "#64748b" };
  }
  const t = Math.max(0.18, count / max); // floor so a single hit is still visible
  return {
    bg: `rgba(59,130,246,${(0.12 + t * 0.4).toFixed(3)})`,
    border: `rgba(96,165,250,${(0.3 + t * 0.5).toFixed(3)})`,
    text: t > 0.55 ? "#f1f5f9" : "#cbd5e1",
  };
}

export function MitreHeatmap({ techniques, className }: MitreHeatmapProps) {
  const items = useMemo(
    () => [...(techniques ?? [])].filter((t) => t?.technique).sort((a, b) => (b.count || 0) - (a.count || 0)),
    [techniques],
  );
  const max = useMemo(() => items.reduce((m, t) => Math.max(m, t.count || 0), 0), [items]);

  return (
    <div className={cn("rounded-xl border border-rw-border bg-rw-elevated p-4", className)}>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm font-semibold text-rw-text">MITRE ATT&CK Coverage</span>
        <span className="ml-auto text-xs text-rw-dim">{items.length} techniques</span>
      </div>

      {items.length === 0 ? (
        <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-rw-border-subtle text-xs text-rw-dim">
          No ATT&CK techniques mapped for this assessment.
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((t) => {
            const shade = cellShade(t.count || 0, max);
            return (
              <div
                key={t.technique}
                className="flex flex-col justify-between gap-2 rounded-lg border p-3 transition-colors"
                style={{ background: shade.bg, borderColor: shade.border }}
                title={`${t.technique} — ${t.count} finding${t.count === 1 ? "" : "s"}`}
              >
                <span className="text-xs font-medium leading-snug" style={{ color: shade.text }}>
                  {t.technique}
                </span>
                <span className="self-end text-lg font-bold tabular-nums" style={{ color: shade.text }}>
                  {t.count}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
