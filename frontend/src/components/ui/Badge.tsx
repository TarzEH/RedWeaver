type BadgeVariant = "default" | "accent" | "success" | "danger" | "warning" | "info";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  dot?: boolean;
  pulseDot?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-slate-500/15 text-slate-400",
  accent: "bg-blue-500/15 text-blue-400",
  success: "bg-emerald-500/15 text-emerald-400",
  danger: "bg-red-500/15 text-red-400",
  warning: "bg-amber-500/15 text-amber-400",
  info: "bg-slate-500/10 text-slate-400",
};

const dotColors: Record<BadgeVariant, string> = {
  default: "bg-slate-400",
  accent: "bg-blue-400",
  success: "bg-emerald-400",
  danger: "bg-red-400",
  warning: "bg-amber-400",
  info: "bg-slate-400",
};

export function Badge({ children, variant = "default", dot, pulseDot, className = "" }: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full
        text-[10px] font-semibold uppercase tracking-wide
        ${variantStyles[variant]} ${className}
      `}
    >
      {dot && (
        <span
          className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]} ${pulseDot ? "animate-pulse-dot" : ""}`}
        />
      )}
      {children}
    </span>
  );
}
