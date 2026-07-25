import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/cn";
import { IconButton } from "./IconButton";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  /** Which edge the panel slides in from. */
  side?: "left" | "right";
  title: string;
  children: React.ReactNode;
  className?: string;
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Overlay panel used to keep a layout's side panes **reachable** when the
 * container is too narrow to dock them. A pane that is one gesture away is
 * fine; a pane that is simply `hidden` with no affordance is a dead end.
 *
 * Positioned `absolute`, so it covers its nearest positioned ancestor (the
 * feature page) rather than the whole app — the global nav stays usable.
 * That ancestor needs `relative`.
 */
export function Drawer({ open, onClose, side = "left", title, children, className }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      // Keep focus inside the panel while it is modal.
      const nodes = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!nodes || nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === panelRef.current)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      restoreFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-40 flex animate-fade-in">
      <div
        role="presentation"
        onClick={onClose}
        className="absolute inset-0 bg-black/60 backdrop-blur-[1px]"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          "relative flex h-full w-[85%] max-w-sm flex-col bg-rw-elevated shadow-2xl outline-none",
          side === "left" ? "border-r border-rw-border" : "ml-auto border-l border-rw-border",
          className,
        )}
      >
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-rw-border px-4 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-rw-dim">{title}</p>
          <IconButton icon={<X size={15} />} label={`Close ${title}`} onClick={onClose} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
