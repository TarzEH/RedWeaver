import { useEffect, useState } from "react";
import { cn } from "../../../lib/cn";
import { formatAge } from "../../../features/dashboard/metrics";

interface FreshnessLabelProps {
  /** Epoch ms of the last successful fetch, or null before the first one. */
  at: number | null;
  /** When paused, the label freezes to a wall-clock time. */
  paused?: boolean;
  /** Prefix, e.g. "spend" → "spend updated 4s ago". */
  subject?: string;
  className?: string;
}

/**
 * How old the data on this panel is.
 *
 * A dashboard that silently serves a stale panel is worse than one that admits
 * it, so every panel states its own age rather than relying on a single global
 * timestamp that may not describe it.
 *
 * While paused, the label stops ticking and switches to the wall-clock time it
 * was captured: a counter that keeps climbing after the user hit pause implies
 * the panel is still doing something, and it is exactly the kind of
 * auto-updating text the pause control exists to stop.
 */
export function FreshnessLabel({ at, paused = false, subject, className }: FreshnessLabelProps) {
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (paused || at === null) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [paused, at]);

  const prefix = subject ? `${subject} ` : "";

  if (at === null) {
    return <span className={cn("text-[11px] text-rw-dim", className)}>{prefix}not loaded yet</span>;
  }

  const text = paused
    ? `frozen at ${new Date(at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
    : `updated ${formatAge(Date.now() - at)}`;

  return (
    <span
      className={cn("text-[11px] tabular-nums text-rw-dim", className)}
      title={`Last fetched ${new Date(at).toLocaleString()}`}
    >
      {prefix}
      {text}
    </span>
  );
}
