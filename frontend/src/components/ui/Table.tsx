import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { Columns3 } from "lucide-react";
import { cn } from "../../lib/cn";

/**
 * Shared table shell. Every data table in the app (hunts, agent steps, event
 * log, asset inventory) used to hand-roll its own header tint, cell padding
 * and hover treatment; these primitives are the one treatment.
 *
 * Wrap in `<Card padding="none" className="overflow-hidden">` for the framed
 * look used across the app.
 *
 * ── Responsive policy ────────────────────────────────────────────────────
 * Tables **scroll, they do not reflow into cards**. Turning rows into cards at
 * a breakpoint destroys cross-row comparison (the entire point of a table),
 * breaks sorting, and throws away the programmatic header/cell association
 * that screen readers rely on. Instead wrap the table in `<TableScroll>`,
 * which gives you a keyboard-reachable scroll region plus scroll shadows.
 *
 * Sizing is driven by **container queries**, not media queries: the same table
 * renders full-width on a page and inside a ~380px side panel at the exact
 * same viewport width, which a media query cannot express.
 */

/* ------------------------------------------------------------------------ */
/* Scroll region                                                             */
/* ------------------------------------------------------------------------ */

interface TableScrollContextValue {
  /** True once the user has asked to see every column. */
  showAll: boolean;
}

const TableScrollContext = createContext<TableScrollContextValue>({ showAll: true });

interface TableScrollProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "children"> {
  /**
   * Accessible name for the scroll region — required for the `role="region"`
   * to be announced as a landmark. Pass `labelledBy` instead if a visible
   * heading already names the table.
   */
  label?: string;
  /** id of an existing visible element that names this region. */
  labelledBy?: string;
  /**
   * Render the "show all columns" toggle. Set this when the table marks any
   * `<TH secondary>` / `<TD secondary>` cells — hiding data with no way back
   * is deletion, not prioritisation.
   */
  collapsible?: boolean;
  /** Class applied to the scrolling element itself (e.g. `max-h-96`). */
  viewportClassName?: string;
  children?: React.ReactNode;
}

/**
 * Keyboard-reachable horizontal scroll region for a `<Table>`.
 *
 * - `role="region"` + `aria-labelledby` gives the scroller an announced name.
 * - `tabIndex={0}` is what lets keyboard-only users scroll it — applied *only*
 *   when the content actually overflows, so we never add a dead tab stop.
 * - Scroll shadows are the affordance: macOS hides scrollbars until the user
 *   interacts, so without them nobody knows there is more table off-screen.
 *
 * ⚠️ This wrapper sets `container-type: inline-size`, which applies inline-size
 * containment: its width comes from its parent, never from the table inside.
 * Inside a flex/grid item, give that item `min-w-0` or the region collapses.
 */
export function TableScroll({
  label,
  labelledBy,
  collapsible,
  className,
  viewportClassName,
  children,
  ...props
}: TableScrollProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const generatedId = useId();
  const labelId = labelledBy ?? (label ? `${generatedId}-label` : undefined);

  const [showAll, setShowAll] = useState(false);
  const [scrollable, setScrollable] = useState(false);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(true);

  const measure = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setScrollable(max > 1);
    setAtStart(el.scrollLeft <= 1);
    setAtEnd(el.scrollLeft >= max - 1);
  }, []);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    measure();
    if (typeof ResizeObserver === "undefined") return;
    // Observe both the viewport and the table: either can change width
    // independently (container resize vs. rows/columns appearing).
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    const table = el.querySelector("table");
    if (table) ro.observe(table);
    return () => ro.disconnect();
  }, [measure, showAll, children]);

  return (
    <TableScrollContext.Provider value={{ showAll }}>
      <div className={cn("@container relative", className)} {...props}>
        {label && (
          <span id={labelId} className="sr-only">
            {label}
          </span>
        )}

        {collapsible && (
          // Only offered while the container is narrow enough for columns to
          // actually be hidden — the same breakpoint the cells use.
          <div className="hidden justify-end px-2 pt-2 @max-2xl:flex">
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              aria-pressed={showAll}
              className={cn(
                "inline-flex min-h-6 items-center gap-1.5 rounded-md px-2 py-1",
                "text-[11px] font-medium transition-colors",
                showAll
                  ? "bg-rw-accent/15 text-rw-accent"
                  : "text-rw-dim hover:bg-rw-surface hover:text-rw-text",
              )}
            >
              <Columns3 size={12} />
              {showAll ? "Fewer columns" : "Show all columns"}
            </button>
          </div>
        )}

        <div
          ref={viewportRef}
          role="region"
          aria-labelledby={labelId}
          // Undersized tables must not become a tab stop that does nothing.
          tabIndex={scrollable ? 0 : undefined}
          onScroll={measure}
          className={cn(
            "overflow-auto",
            "focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-rw-accent focus-visible:outline-none",
            viewportClassName,
          )}
        >
          {children}
        </div>

        {/* Scroll shadows — the "there is more" affordance. */}
        <div
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-y-0 left-0 w-6 transition-opacity duration-150",
            "bg-gradient-to-r from-rw-bg/90 to-transparent",
            scrollable && !atStart ? "opacity-100" : "opacity-0",
          )}
        />
        <div
          aria-hidden="true"
          className={cn(
            "pointer-events-none absolute inset-y-0 right-0 w-6 transition-opacity duration-150",
            "bg-gradient-to-l from-rw-bg/90 to-transparent",
            scrollable && !atEnd ? "opacity-100" : "opacity-0",
          )}
        />
      </div>
    </TableScrollContext.Provider>
  );
}

/** Cells marked `secondary` collapse below @2xl unless "show all" is on. */
function useSecondaryClass(secondary?: boolean) {
  const { showAll } = useContext(TableScrollContext);
  return secondary && !showAll ? "@max-2xl:hidden" : undefined;
}

/* ------------------------------------------------------------------------ */
/* Table                                                                     */
/* ------------------------------------------------------------------------ */

interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  /** Pin the header row while the body scrolls vertically. */
  stickyHeader?: boolean;
  /** Pin the first column while the body scrolls horizontally. */
  stickyFirstCol?: boolean;
}

/**
 * Sticky cells lose collapsed borders (a collapsed border belongs to the table,
 * not the cell, so it does not travel with a sticky cell). Whenever anything is
 * sticky we switch to `border-separate` and move the row rule onto the cells.
 *
 * z-index ladder — corner > header row > first column > body:
 *   corner (thead th:first-child)  z-30
 *   header row (thead th)          z-20
 *   first column (tbody td)        z-10
 *   body                           auto
 */
const stickyHeaderStyles = [
  "[&_thead_th]:sticky [&_thead_th]:top-0 [&_thead_th]:z-20 [&_thead_th]:bg-rw-elevated",
].join(" ");

const stickyFirstColStyles = [
  "[&_tbody_td:first-child]:sticky [&_tbody_td:first-child]:left-0",
  "[&_tbody_td:first-child]:z-10 [&_tbody_td:first-child]:bg-rw-elevated",
  "[&_tbody_tr:hover>td:first-child]:bg-rw-surface",
  "[&_thead_th:first-child]:sticky [&_thead_th:first-child]:left-0",
  "[&_thead_th:first-child]:z-30 [&_thead_th:first-child]:bg-rw-elevated",
].join(" ");

// `border-separate` kills the <tr> border, so re-draw the row rule on cells.
const separatedBorderStyles = [
  "border-separate border-spacing-0",
  "[&_tbody_tr>*]:border-t [&_tbody_tr>*]:border-rw-border/60",
].join(" ");

export function Table({ children, className, stickyHeader, stickyFirstCol, ...props }: TableProps) {
  const anySticky = stickyHeader || stickyFirstCol;
  return (
    <table
      className={cn(
        "w-full text-sm",
        anySticky && separatedBorderStyles,
        stickyHeader && stickyHeaderStyles,
        stickyFirstCol && stickyFirstColStyles,
        className,
      )}
      {...props}
    >
      {children}
    </table>
  );
}

export function THead({ children, className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn(
        "bg-rw-surface/50 text-left text-[11px] font-medium uppercase tracking-wide text-rw-dim",
        className,
      )}
      {...props}
    >
      {children}
    </thead>
  );
}

interface THProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  /** Lower-priority column: collapses in narrow containers, restorable via the toggle. */
  secondary?: boolean;
}

export function TH({ children, className, secondary, ...props }: THProps) {
  return (
    <th className={cn("px-4 py-2.5 font-medium", useSecondaryClass(secondary), className)} {...props}>
      {children}
    </th>
  );
}

export function TBody({ children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...props}>{children}</tbody>;
}

interface TRProps extends React.HTMLAttributes<HTMLTableRowElement> {
  /** Row is clickable — adds the hover/cursor/focus affordances. */
  interactive?: boolean;
}

export function TR({ children, className, interactive, ...props }: TRProps) {
  return (
    <tr
      className={cn(
        "border-t border-rw-border/60 transition-colors",
        interactive &&
          "cursor-pointer outline-none hover:bg-rw-surface/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-rw-accent",
        className,
      )}
      {...props}
    >
      {children}
    </tr>
  );
}

interface TDProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  /** Must mirror the matching `<TH secondary>` so the column collapses as a unit. */
  secondary?: boolean;
}

export function TD({ children, className, secondary, ...props }: TDProps) {
  return (
    <td className={cn("px-4 py-2.5 align-middle", useSecondaryClass(secondary), className)} {...props}>
      {children}
    </td>
  );
}
