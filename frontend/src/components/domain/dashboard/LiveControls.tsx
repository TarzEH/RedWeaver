import { Pause, Play, RotateCw } from "lucide-react";
import { Button } from "../../ui/Button";
import { cn } from "../../../lib/cn";

interface LiveControlsProps {
  live: boolean;
  onToggle: (next: boolean) => void;
  /** Manual fetch — the way to get fresh data while paused. */
  onRefresh: () => void;
  /** True while a hunt is running, i.e. while the poll would actually fire. */
  polling: boolean;
  className?: string;
}

/**
 * Live / Paused, plus a manual refresh.
 *
 * This is a conformance requirement, not a nicety: WCAG 2.2.2 (Level A) says
 * auto-updating information must come with a mechanism to pause, stop or hide
 * it. A dashboard that repolls every 5 seconds with no way to stop it fails at
 * Level A — it also yanks the ground out from under anyone using a screen
 * magnifier or reading a row they were half-way through.
 *
 * Pausing is a real stop, not a visual freeze: the poll interval is cleared, so
 * nothing is fetched and nothing re-renders behind the reader's back.
 */
export function LiveControls({ live, onToggle, onRefresh, polling, className }: LiveControlsProps) {
  return (
    <div className={cn("flex items-center gap-1.5", className)}>
      <Button
        variant="secondary"
        size="sm"
        aria-pressed={live}
        onClick={() => onToggle(!live)}
        title={
          live
            ? "Pause auto-refresh — the dashboard will stop fetching until you resume"
            : "Resume auto-refresh every 5 seconds while a hunt is running"
        }
        icon={live ? <Pause size={13} aria-hidden /> : <Play size={13} aria-hidden />}
      >
        {/* The word is the state; the dot and icon only reinforce it. */}
        <span
          aria-hidden
          className={cn(
            "h-1.5 w-1.5 shrink-0 rounded-full",
            live ? (polling ? "bg-emerald-400" : "bg-slate-400") : "bg-amber-400",
          )}
        />
        {live ? "Live" : "Paused"}
        <span className="sr-only">
          {live
            ? polling
              ? " — auto-refresh on, refreshing every 5 seconds. Activate to pause."
              : " — auto-refresh on, idle until a hunt starts. Activate to pause."
            : " — auto-refresh paused. Activate to resume."}
        </span>
      </Button>

      <Button
        variant="ghost"
        size="sm"
        onClick={onRefresh}
        title="Fetch the latest data now"
        icon={<RotateCw size={13} aria-hidden />}
      >
        <span className="sr-only">Refresh now</span>
      </Button>
    </div>
  );
}
