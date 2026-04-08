import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

const toneStyles = {
  primary: "bg-primary/10 text-primary",
  success: "bg-emerald-500/10 text-emerald-400",
  warning: "bg-amber-500/10 text-amber-400",
  danger: "bg-error/10 text-error",
  info: "bg-blue-400/10 text-blue-400",
  neutral: "bg-white/5 text-stone-400",
} as const;

export interface BadgeProps {
  tone?: keyof typeof toneStyles;
  pulse?: boolean;
  children?: ReactNode;
  className?: string;
}

export function Badge({
  tone = "primary",
  pulse = false,
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center text-[10px] font-black uppercase px-2 py-0.5 rounded",
        toneStyles[tone],
        pulse && "animate-pulse",
        className,
      )}
    >
      {children}
    </span>
  );
}
