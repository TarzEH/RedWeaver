import { cn } from "../../lib/cn";

/**
 * Responsive grid for stat/metric tiles.
 *
 * Replaces the hand-rolled `<div className="grid grid-cols-4 gap-4">` rows,
 * which stayed four-across at *every* width — at 375px that renders ~80px per
 * tile, so labels silently truncate to "Complete" and "Runnin" and the
 * overflowing content is clipped rather than scrolled.
 *
 * ── Why container queries and not `sm:` / `md:` ──────────────────────────
 * The same stat row appears full-width on the dashboard and inside a ~380px
 * side panel *at the same viewport width*. A media query only knows about the
 * viewport, so it gets one of those two cases wrong no matter how it is tuned.
 * These breakpoints key off the width this component was actually given.
 *
 * ⚠️ Landmines, in case you extend this:
 *  - `@container` sets `container-type: inline-size`, which applies inline-size
 *    containment. An element cannot query *itself*, so the container and the
 *    grid must be two elements — hence the wrapper div here.
 *  - Do not make a CSS Grid *item* the container; wrap the item's contents.
 *  - Never give a Recharts chart a percentage height inside a container. The
 *    containment resolves it against zero and the chart vanishes. Use fixed
 *    per-breakpoint heights (`h-56 @lg:h-64`).
 */

interface StatGridProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Widest layout to grow into. Narrower containers step down to 2, then 1. */
  columns?: 2 | 3 | 4;
  /** Class applied to the grid element (the container wrapper takes `className`). */
  gridClassName?: string;
}

// Stepped so each tile keeps ~160px+ of usable width before adding a column.
const columnSteps: Record<NonNullable<StatGridProps["columns"]>, string> = {
  2: "grid-cols-1 @sm:grid-cols-2",
  3: "grid-cols-1 @sm:grid-cols-2 @xl:grid-cols-3",
  4: "grid-cols-1 @sm:grid-cols-2 @2xl:grid-cols-4",
};

export function StatGrid({
  columns = 4,
  className,
  gridClassName,
  children,
  ...props
}: StatGridProps) {
  return (
    <div className={cn("@container", className)} {...props}>
      <div className={cn("grid gap-4", columnSteps[columns], gridClassName)}>{children}</div>
    </div>
  );
}
