interface CardProps {
  children: React.ReactNode;
  className?: string;
  glow?: "accent" | "danger" | "success";
  padding?: "none" | "sm" | "md" | "lg";
}

const glowStyles: Record<string, string> = {
  accent: "shadow-[0_0_20px_rgba(59,130,246,0.08)]",
  danger: "shadow-[0_0_20px_rgba(239,68,68,0.06)]",
  success: "shadow-[0_0_20px_rgba(16,185,129,0.06)]",
};

const paddingStyles: Record<string, string> = {
  none: "",
  sm: "p-3",
  md: "p-4",
  lg: "p-6",
};

export function Card({ children, className = "", glow, padding = "md" }: CardProps) {
  return (
    <div
      className={`
        bg-rw-elevated border border-rw-border rounded-xl
        ${glow ? glowStyles[glow] : ""}
        ${paddingStyles[padding]}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export function CardHeader({ icon, title, subtitle, action }: CardHeaderProps) {
  return (
    <div className="flex items-center gap-2 mb-3">
      {icon && <span className="text-rw-accent">{icon}</span>}
      <div className="flex-1">
        <h3 className="text-sm font-semibold text-rw-text">{title}</h3>
        {subtitle && <p className="text-xs text-rw-dim mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
