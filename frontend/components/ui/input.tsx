"use client";

import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
  error?: string;
  icon?: ReactNode;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, hint, error, icon, id, ...props }, ref) => {
    const inputId = id ?? (label ? `input-${label.toLowerCase().replace(/\s+/g, "-")}` : undefined);
    const hintId = hint && inputId ? `${inputId}-hint` : undefined;
    const errorId = error && inputId ? `${inputId}-error` : undefined;

    const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;

    return (
      <div className={cn("ds-field", error && "ds-field--error", className)}>
        {label ? (
          <label className="ds-field__label" htmlFor={inputId}>
            {label}
          </label>
        ) : null}
        <div className="ds-field__wrap">
          {icon ? (
            <span aria-hidden="true" className="ds-field__icon">
              {icon}
            </span>
          ) : null}
          <input
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
            className={cn("ds-field__input", icon && "ds-field__input--icon")}
            id={inputId}
            ref={ref}
            {...props}
          />
        </div>
        {hint && !error ? (
          <span className="ds-field__hint" id={hintId}>
            {hint}
          </span>
        ) : null}
        {error ? (
          <span aria-live="polite" className="ds-field__error" id={errorId} role="alert">
            {error}
          </span>
        ) : null}
      </div>
    );
  },
);

Input.displayName = "Input";
