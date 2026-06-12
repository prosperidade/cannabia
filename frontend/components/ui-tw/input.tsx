import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/cn";
import { MaterialIcon } from "./material-icon";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  icon?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, error, icon, className, id, ...rest }, ref) => {
    const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[10px] uppercase tracking-widest text-stone-400 font-bold"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-500">
              <MaterialIcon icon={icon} size="sm" />
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors",
              icon && "pl-10",
              error && "border-error/50",
              className,
            )}
            {...rest}
          />
        </div>
        {error && <span className="text-[11px] text-error font-medium">{error}</span>}
        {hint && !error && <span className="text-[11px] text-stone-500">{hint}</span>}
      </div>
    );
  },
);

Input.displayName = "Input";
