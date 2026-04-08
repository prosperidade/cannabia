import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { MaterialIcon } from "./material-icon";

const variantStyles = {
  primary:
    "bg-primary text-on-primary-container font-bold hover:brightness-110 shadow-lg shadow-primary-container/20",
  secondary:
    "border border-primary/30 bg-primary/10 text-primary font-bold hover:brightness-110",
  ghost: "text-stone-400 hover:bg-white/5 font-bold",
  danger:
    "bg-error/10 text-error border border-error/30 font-bold hover:brightness-110",
} as const;

const sizeStyles = {
  sm: "px-4 py-2 text-xs gap-1.5",
  md: "px-6 py-3 text-sm gap-2",
  lg: "px-8 py-4 text-base gap-2.5",
} as const;

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  loading?: boolean;
  icon?: string;
  children?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      icon,
      children,
      className,
      disabled,
      ...rest
    },
    ref,
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center rounded-lg transition-all active:scale-95 uppercase tracking-widest font-headline",
          "disabled:opacity-50 disabled:pointer-events-none",
          variantStyles[variant],
          sizeStyles[size],
          className,
        )}
        {...rest}
      >
        {loading ? (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : icon ? (
          <MaterialIcon icon={icon} size="sm" />
        ) : null}
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";
