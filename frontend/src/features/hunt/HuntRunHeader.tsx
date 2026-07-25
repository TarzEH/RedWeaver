import { Crosshair, FolderOpen, Square, Trash2 } from "lucide-react";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { IconButton } from "../../components/ui/IconButton";
import { useConfirm } from "../../components/ui/feedback";
import { formatTokens, formatUsd, toNumber } from "../../lib/money";
import { cn } from "../../lib/cn";
import type { RunDetail } from "../../types/api";

interface HuntRunHeaderProps {
  run: RunDetail;
  /** True while the SSE socket is attached — drives the LIVE marker. */
  live: boolean;
  /** True while the run is queued/running, i.e. Stop is meaningful. */
  stoppable: boolean;
  stopping: boolean;
  deleting: boolean;
  onStop: () => void;
  onDelete: () => void;
}

/**
 * Identity + live economics for the selected run.
 *
 * `cost_usd` / `budget_usd` arrive as DRF decimal *strings*, so every number
 * here goes through `toNumber`/`formatUsd` — arithmetic on the raw value would
 * concatenate instead of add.
 */
export function HuntRunHeader({
  run,
  live,
  stoppable,
  stopping,
  deleting,
  onStop,
  onDelete,
}: HuntRunHeaderProps) {
  const confirm = useConfirm();

  const cost = toNumber(run.cost_usd);
  const budget = toNumber(run.budget_usd);
  const hasSpend = cost !== null && cost > 0;
  // A budget of 0/absent means "no ceiling" — don't render a meter against it.
  const spentFraction = budget && budget > 0 && cost !== null ? cost / budget : null;
  const overBudget = spentFraction !== null && spentFraction >= 1;

  const confirmStop = async () => {
    const ok = await confirm({
      title: "Stop this hunt?",
      message:
        "The agents stop where they are. Everything already found is kept, and the run is marked Stopped.",
      confirmLabel: "Stop hunt",
    });
    if (ok) onStop();
  };

  return (
    <div className="border-b border-rw-border bg-rw-elevated animate-fade-in">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2 text-sm">
        <Crosshair size={14} className="shrink-0 text-rw-accent" aria-hidden />
        <span className="font-mono text-xs text-rw-text">{run.target}</span>
        {run.scope && <span className="text-xs text-rw-dim">Scope: {run.scope}</span>}
        <StatusBadge status={run.status} />
        {run.session_id && (
          <span
            className="inline-flex items-center gap-1 rounded border border-rw-accent/20 bg-rw-accent/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-rw-accent/90"
            title={
              run.workspace_name && run.session_name
                ? `${run.workspace_name} · ${run.session_name}`
                : run.session_name ?? "Workspace session"
            }
          >
            <FolderOpen size={11} aria-hidden />
            Project
          </span>
        )}
        {live && (
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
            LIVE
          </span>
        )}

        <div className="ml-auto flex items-center gap-1">
          {stoppable && (
            <button
              type="button"
              onClick={confirmStop}
              disabled={stopping}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border border-rw-border px-2.5 py-1",
                "text-[11px] font-medium text-rw-muted transition-colors",
                "hover:border-red-500/40 hover:text-red-400",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent",
                "disabled:cursor-not-allowed disabled:opacity-40",
              )}
            >
              <Square size={11} aria-hidden />
              {stopping ? "Stopping…" : "Stop"}
            </button>
          )}
          <IconButton
            icon={<Trash2 size={14} />}
            label="Delete hunt"
            variant="danger"
            onClick={onDelete}
            disabled={deleting}
            className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rw-accent"
          />
        </div>
      </div>

      {/* Spend — the run object is already polled every 3s, so this is live. */}
      {(hasSpend || (budget !== null && budget > 0)) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-rw-border/60 px-4 py-1.5">
          <span className="text-[10px] uppercase tracking-wider text-rw-dim">Spend</span>
          <span
            className={cn(
              "font-mono text-xs tabular-nums",
              overBudget ? "text-orange-400" : "text-rw-text",
            )}
          >
            {formatUsd(run.cost_usd)}
          </span>
          {budget !== null && budget > 0 && (
            <>
              <span className="text-xs text-rw-dim">
                of <span className="font-mono tabular-nums">{formatUsd(budget)}</span> limit
              </span>
              <span
                className="h-1.5 w-24 overflow-hidden rounded-full bg-rw-surface"
                role="img"
                aria-label={`${Math.round((spentFraction ?? 0) * 100)} percent of the spend limit used`}
              >
                <span
                  className={cn(
                    "block h-full rounded-full transition-[width] duration-500",
                    overBudget ? "bg-orange-400" : "bg-rw-accent",
                  )}
                  style={{ width: `${Math.min(100, Math.max(2, (spentFraction ?? 0) * 100))}%` }}
                />
              </span>
              {/* Never colour-only: the bar turning orange is restated in words. */}
              <span
                className={cn(
                  "text-[11px] font-medium tabular-nums",
                  overBudget ? "text-orange-400" : "text-rw-dim",
                )}
              >
                {Math.round((spentFraction ?? 0) * 100)}% used{overBudget ? " — limit reached" : ""}
              </span>
            </>
          )}
          {run.total_tokens != null && (
            <span className="text-xs text-rw-dim">
              <span className="font-mono tabular-nums">{formatTokens(run.total_tokens)}</span> tokens
            </span>
          )}
        </div>
      )}

      {/* Why it stopped early — a budget abort or a real failure. */}
      {run.error_message && (
        <p className="border-t border-rw-border/60 px-4 py-1.5 text-[11px] text-orange-400">
          <span className="font-medium">Run note:</span> {run.error_message}
        </p>
      )}
    </div>
  );
}
