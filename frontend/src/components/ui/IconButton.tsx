import { forwardRef } from "react";

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  label: string;
  size?: "sm" | "md";
  variant?: "default" | "danger";
}

const sizeStyles = {
  sm: "w-8 h-8",
  md: "w-10 h-10",
};

const variantStyles = {
  default: "text-rw-dim hover:text-rw-muted hover:bg-rw-surface",
  danger: "text-rw-dim hover:text-red-400 hover:bg-red-500/10",
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ icon, label, size = "sm", variant = "default", className = "", ...props }, ref) => {
    return (
      <button
        ref={ref}
        title={label}
        aria-label={label}
        className={`
          inline-flex items-center justify-center rounded-lg
          transition-colors duration-150
          ${sizeStyles[size]} ${variantStyles[variant]} ${className}
        `}
        {...props}
      >
        {icon}
      </button>
    );
  },
);

IconButton.displayName = "IconButton";
