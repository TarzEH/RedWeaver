import { DollarSign } from "lucide-react";
import type { ReportCost } from "../../../types/api";
import { cn } from "../../../lib/cn";

interface CostBadgeProps {
  /** The report's `cost` block. Render only when `total_usd` is present. */
  cost: ReportCost;
  className?: string;
}

/**
 * What a hunt cost, and how much of its ceiling it used.
 *
 * Two things this deliberately makes visible rather than smoothing over:
 * an unpriced model produces a fallback-rate guess (marked, not presented as
 * fact), and a run that hit its ceiling stopped early — so its report is
 * partial, which is worth knowing before reading the findings.
 */

/** Sub-dollar runs are the common case; two decimals would round them to $0.00. */
function formatUsd(value: number): string {
  return value < 1 ? value.toFixed(4) : value.toFixed(2);
}

export function CostBadge({ cost, className }: CostBadgeProps) {
  const spent = cost.total_usd ?? 0;
  const budget = cost.budget_usd ?? null;
  const used = cost.budget_used_fraction ?? null;
  const overBudget = used != null && used >= 1;
  const isEstimate = cost.is_estimate === true;

  const tokens = cost.total_tokens ?? null;
  const estimateNote = isEstimate
    ? "No price is on file for this model, so the figure is a fallback-rate estimate"
    : undefined;

  return (
    <span className={cn("flex flex-col items-end gap-1", className)}>
      <span className="inline-flex items-center gap-1.5 rounded-md border border-rw-border bg-rw-surface/50 px-2.5 py-1 text-xs text-rw-muted">
        <DollarSign size={13} className="text-rw-dim" aria-hidden />
        <span className="tabular-nums" title={estimateNote}>
          {isEstimate && <span aria-hidden>~</span>}
          {formatUsd(spent)}
          {isEstimate && <span className="sr-only"> (estimated)</span>}
        </span>

        {budget != null && (
          <span
            className={cn("tabular-nums", overBudget ? "text-rw-danger" : "text-rw-dim")}
            title={`Spend ceiling for this run: $${budget.toFixed(2)}`}
          >
            / {budget.toFixed(2)}
          </span>
        )}

        {isEstimate && (
          <span className="text-rw-dim" title={estimateNote}>
            est.
          </span>
        )}
      </span>

      {(cost.model || tokens != null) && (
        <span className="flex items-center gap-1.5 text-[11px] text-rw-dim">
          {cost.model && <span className="font-mono">{cost.model}</span>}
          {cost.model && tokens != null && <span aria-hidden>·</span>}
          {tokens != null && (
            <span className="tabular-nums" title="Prompt + completion tokens">
              {tokens.toLocaleString()} tokens
            </span>
          )}
        </span>
      )}

      {used != null && (
        <span className="flex items-center gap-1.5">
          <span
            role="img"
            aria-label={`${Math.round(used * 100)} percent of the spend ceiling used`}
            className="h-1 w-24 overflow-hidden rounded-full bg-rw-surface"
          >
            <span
              className={cn(
                "block h-full rounded-full",
                overBudget ? "bg-rw-danger" : "bg-rw-accent",
              )}
              style={{ width: `${Math.min(100, used * 100)}%` }}
            />
          </span>
          {/* The word carries the meaning; the red is only reinforcement. */}
          <span
            className={cn("text-[11px] tabular-nums", overBudget ? "text-rw-danger" : "text-rw-dim")}
          >
            {overBudget
              ? "ceiling reached — hunt stopped early"
              : `${Math.round(used * 100)}% of budget`}
          </span>
        </span>
      )}
    </span>
  );
}
