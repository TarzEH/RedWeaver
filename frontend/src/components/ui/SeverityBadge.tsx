import { severityStyle, severityHex } from "../../config/theme";
import { cn } from "../../lib/cn";
import type { Severity } from "../../types/api";

interface SeverityBadgeProps {
  severity: Severity;
  /**
   * Render a colour chip next to the label. The written label is always
   * present — the chip is a redundant cue, never the only signal.
   */
  dot?: boolean;
  className?: string;
}

/**
 * The single severity chip for the whole app. Styling comes from
 * `severityStyle()` in config/theme so the in-app palette, the charts
 * (`severityHex`) and the exported report stay on one set of tokens.
 */
export function SeverityBadge({ severity, dot = false, className = "" }: SeverityBadgeProps) {
  const s = severityStyle(severity);
  return (
    <span
      title={`${s.label} severity`}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded border px-1.5 py-0.5",
        "text-[10px] font-bold uppercase tracking-wide",
        s.bg,
        s.color,
        s.border,
        className,
      )}
    >
      {dot && (
        <span
          aria-hidden
          className="h-1.5 w-1.5 shrink-0 rounded-full"
          style={{ backgroundColor: severityHex(severity) }}
        />
      )}
      {s.label}
    </span>
  );
}
