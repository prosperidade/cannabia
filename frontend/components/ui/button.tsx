"use client";

import { Slot } from "@radix-ui/react-slot";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  asChild?: boolean;
  loading?: boolean;
  icon?: ReactNode;
};

const variantClass: Record<ButtonVariant, string> = {
  primary: "ds-btn--primary",
  secondary: "ds-btn--secondary",
  ghost: "ds-btn--ghost",
  danger: "ds-btn--danger",
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "ds-btn--sm",
  md: "ds-btn--md",
  lg: "ds-btn--lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = "primary",
      size = "md",
      asChild = false,
      loading = false,
      disabled,
      icon,
      children,
      ...props
    },
    ref,
  ) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        aria-busy={loading || undefined}
        aria-disabled={disabled || loading || undefined}
        className={cn(
          "ds-btn",
          variantClass[variant],
          sizeClass[size],
          loading && "ds-btn--loading",
          className,
        )}
        disabled={disabled || loading}
        ref={ref}
        type={asChild ? undefined : "button"}
        {...props}
      >
        {loading ? (
          <>
            <span aria-hidden="true" className="ds-btn__spinner" />
            <span className="sr-only">Carregando...</span>
          </>
        ) : null}
        {icon && !loading ? (
          <span aria-hidden="true" className="ds-btn__icon">
            {icon}
          </span>
        ) : null}
        {children}
      </Comp>
    );
  },
);

Button.displayName = "Button";
