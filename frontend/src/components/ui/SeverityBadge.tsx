import type { Severity } from "../../types/api";

interface SeverityBadgeProps {
  severity: Severity;
  className?: string;
}

const styles: Record<Severity, string> = {
  critical: "bg-red-500/15 text-red-400 border-red-500/25",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  low: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  info: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

export function SeverityBadge({ severity, className = "" }: SeverityBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center px-1.5 py-0.5 rounded text-[10px]
        font-bold uppercase tracking-wide border
        ${styles[severity]} ${className}
      `}
    >
      {severity}
    </span>
  );
}
