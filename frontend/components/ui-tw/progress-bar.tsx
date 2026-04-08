import { cn } from "@/lib/cn";

const variantColors = {
  primary: "bg-primary",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-error",
} as const;

const variantGlows = {
  primary: "shadow-[0_0_8px_rgba(190,230,84,0.5)]",
  success: "shadow-[0_0_8px_rgba(16,185,129,0.5)]",
  warning: "shadow-[0_0_8px_rgba(245,158,11,0.5)]",
  danger: "shadow-[0_0_8px_rgba(255,180,171,0.5)]",
} as const;

const sizeStyles = {
  sm: "h-1.5",
  md: "h-2.5",
} as const;

export interface ProgressBarProps {
  value: number;
  variant?: keyof typeof variantColors;
  size?: keyof typeof sizeStyles;
  glow?: boolean;
  className?: string;
}

export function ProgressBar({
  value,
  variant = "primary",
  size = "md",
  glow = false,
  className,
}: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div
      className={cn(
        "w-full bg-surface-container-highest rounded-full overflow-hidden",
        sizeStyles[size],
        className,
      )}
    >
      <div
        className={cn(
          "h-full rounded-full transition-all duration-500 ease-out",
          variantColors[variant],
          glow && variantGlows[variant],
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
