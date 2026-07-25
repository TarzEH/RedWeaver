import { CheckCircle2, XCircle, ShieldOff, Wrench, type LucideIcon } from "lucide-react";

/** Adjudication verdict written onto a finding by the verification pass. */
interface FindingStatusBadgeProps {
  /** Finding.status — "new"/unset renders nothing (default state, no badge noise). */
  status?: string;
  /** Finding.verified_by_agent — surfaced in the tooltip. */
  verifiedBy?: string;
  /** Tighter type/padding for the embedded (compact) findings list. */
  compact?: boolean;
  className?: string;
}

interface StatusMeta {
  label: string;
  icon: LucideIcon;
  hint: string;
  cls: string;
}

/** Colour is never the only signal: every verdict carries its own icon + word. */
const STATUS_META: Record<string, StatusMeta> = {
  confirmed: {
    label: "Confirmed",
    icon: CheckCircle2,
    hint: "survived an attempt to refute it against its own evidence",
    cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  },
  false_positive: {
    label: "Ruled out",
    icon: XCircle,
    hint: "refuted against its own evidence — false positive",
    cls: "bg-rw-surface text-rw-dim border-rw-border border-dashed",
  },
  accepted_risk: {
    label: "Accepted risk",
    icon: ShieldOff,
    hint: "real, but knowingly accepted",
    cls: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  },
  remediated: {
    label: "Remediated",
    icon: Wrench,
    hint: "already fixed",
    cls: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  },
};

/** True when the verification pass refuted this finding. */
export function isRuledOut(status?: string): boolean {
  return status === "false_positive";
}

export function FindingStatusBadge({
  status,
  verifiedBy,
  compact = false,
  className = "",
}: FindingStatusBadgeProps) {
  const meta = status ? STATUS_META[status] : undefined;
  // "new" (and anything unrecognised) stays silent — no badge on the default state.
  if (!meta) return null;

  const Icon = meta.icon;
  const title = `${meta.label} — ${meta.hint}. ${
    verifiedBy ? `Verified by ${verifiedBy}` : "No verifying agent recorded"
  }`;

  return (
    <span
      title={title}
      className={`
        inline-flex shrink-0 items-center gap-1 rounded border font-medium
        ${compact ? "px-1 py-0.5 text-[9px]" : "px-1.5 py-0.5 text-[10px]"}
        ${meta.cls} ${className}
      `}
    >
      <Icon size={compact ? 9 : 10} aria-hidden="true" className="shrink-0" />
      {meta.label}
    </span>
  );
}
