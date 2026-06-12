import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

const variantStyles = {
  glass: "glass-panel rounded-2xl",
  solid: "bg-surface-container rounded-2xl border border-white/5",
  outline: "border border-outline-variant/30 rounded-2xl",
} as const;

const paddingStyles = {
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
} as const;

export interface CardProps {
  variant?: keyof typeof variantStyles;
  padding?: keyof typeof paddingStyles;
  children?: ReactNode;
  className?: string;
}

export function Card({ variant = "glass", padding = "md", children, className }: CardProps) {
  return (
    <div className={cn(variantStyles[variant], paddingStyles[padding], className)}>{children}</div>
  );
}
