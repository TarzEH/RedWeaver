import { forwardRef } from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ icon, error, className = "", ...props }, ref) => {
    return (
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-rw-dim pointer-events-none">
            {icon}
          </span>
        )}
        <input
          ref={ref}
          className={`
            w-full bg-rw-input border rounded-lg text-sm text-rw-text
            placeholder-rw-dim outline-none transition-colors duration-150
            focus:border-rw-accent/50 focus:ring-1 focus:ring-rw-accent/20
            ${icon ? "pl-9 pr-3" : "px-3"} py-2.5
            ${error ? "border-red-500/50" : "border-rw-border"}
            ${className}
          `}
          {...props}
        />
        {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
      </div>
    );
  },
);

Input.displayName = "Input";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ options, className = "", ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={`
          bg-rw-input border border-rw-border rounded-lg px-3 py-2.5
          text-sm text-rw-text outline-none transition-colors duration-150
          focus:border-rw-accent/50 focus:ring-1 focus:ring-rw-accent/20
          ${className}
        `}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    );
  },
);

Select.displayName = "Select";
