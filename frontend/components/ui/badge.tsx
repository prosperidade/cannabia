import { cn } from "@/lib/cn";

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

type BadgeProps = {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
  /** Pulse animation for live statuses */
  pulse?: boolean;
};

const toneClass: Record<BadgeTone, string> = {
  neutral: "ds-badge--neutral",
  success: "ds-badge--success",
  warning: "ds-badge--warning",
  danger: "ds-badge--danger",
  info: "ds-badge--info",
};

export function Badge({ children, tone = "neutral", pulse = false, className }: BadgeProps) {
  return (
    <span className={cn("ds-badge", toneClass[tone], pulse && "ds-badge--pulse", className)}>
      {pulse ? <span aria-hidden="true" className="ds-badge__dot" /> : null}
      {children}
    </span>
  );
}
