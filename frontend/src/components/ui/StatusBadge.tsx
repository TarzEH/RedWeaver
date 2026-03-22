import { statusLabel, statusColor } from "../../config/theme";
import type { RunStatus } from "../../types/api";

interface StatusBadgeProps {
  status: RunStatus;
  showDot?: boolean;
}

export function StatusBadge({ status, showDot = true }: StatusBadgeProps) {
  const sc = statusColor(status);
  const isRunning = status === "running";

  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ color: sc.color, background: sc.bg }}
    >
      {showDot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${isRunning ? "animate-pulse-dot" : ""}`}
          style={{ background: sc.color }}
        />
      )}
      {statusLabel(status)}
    </span>
  );
}
