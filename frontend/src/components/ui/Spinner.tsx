type SpinnerSize = "xs" | "sm" | "md" | "lg";

interface SpinnerProps {
  size?: SpinnerSize;
  label?: string;
  className?: string;
}

const sizeStyles: Record<SpinnerSize, string> = {
  xs: "w-3 h-3 border",
  sm: "w-4 h-4 border-2",
  md: "w-6 h-6 border-2",
  lg: "w-8 h-8 border-2",
};

export function Spinner({ size = "sm", label, className = "" }: SpinnerProps) {
  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      <div
        className={`
          border-rw-accent/30 border-t-rw-accent rounded-full animate-spin
          ${sizeStyles[size]}
        `}
      />
      {label && <span className="text-sm text-rw-dim">{label}</span>}
    </div>
  );
}

/** Full-page centered spinner */
export function PageSpinner() {
  return (
    <div className="h-screen bg-rw-bg flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
}
