import { cn } from "../../lib/cn";

/**
 * Shared table shell. Every data table in the app (hunts, agent steps, event
 * log, asset inventory) used to hand-roll its own header tint, cell padding
 * and hover treatment; these primitives are the one treatment.
 *
 * Wrap in `<Card padding="none" className="overflow-hidden">` for the framed
 * look used across the app.
 */

export function Table({ children, className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <table className={cn("w-full text-sm", className)} {...props}>
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

export function TH({ children, className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th className={cn("px-4 py-2.5 font-medium", className)} {...props}>
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

export function TD({ children, className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className={cn("px-4 py-2.5 align-middle", className)} {...props}>
      {children}
    </td>
  );
}
