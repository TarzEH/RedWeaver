import { forwardRef, useId } from "react";
import { cn } from "../../lib/cn";

/**
 * One field treatment for the whole app — surface, radius, focus ring.
 * The ring is 2px at high opacity so the focused field is unmistakable
 * (the old 1px/20% ring was effectively invisible on the dark surface).
 *
 * Exported for the handful of bare `<input>`s that cannot use `<Input>` because
 * they need to be a flex/grid item themselves (Input wraps in a positioning
 * div for its icon slot). Compose with `cn()` — tailwind-merge lets the caller's
 * width/padding/size win while the surface and focus ring stay canonical.
 */
export const fieldBase =
  "w-full rounded-lg border bg-rw-input text-sm text-rw-text " +
  "placeholder-rw-dim outline-none transition-colors duration-150 " +
  "focus:border-rw-accent focus:ring-2 focus:ring-rw-accent/60 " +
  "disabled:cursor-not-allowed disabled:opacity-40";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ icon, error, className = "", id, ...props }, ref) => {
    const autoId = useId();
    const inputId = id ?? autoId;
    const errorId = `${inputId}-error`;
    return (
      <div className="relative">
        {icon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-rw-dim">
            {icon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            fieldBase,
            "py-2.5",
            icon ? "pl-9 pr-3" : "px-3",
            error ? "border-red-500/60" : "border-rw-border",
            className,
          )}
          {...props}
        />
        {error && (
          <p id={errorId} className="mt-1 text-xs text-red-400">
            {error}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;

/** Same field treatment as Input, for multi-line entry. */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(fieldBase, "resize-none border-rw-border px-3 py-2", className)}
      {...props}
    />
  ),
);

Textarea.displayName = "Textarea";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  options: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ options, className = "", children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={cn(fieldBase, "cursor-pointer border-rw-border px-3 py-2.5", className)}
        {...props}
      >
        {children}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-rw-elevated">
            {opt.label}
          </option>
        ))}
      </select>
    );
  },
);

Select.displayName = "Select";
