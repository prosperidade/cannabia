import { forwardRef, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  padding?: "sm" | "md" | "lg";
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, padding = "md", children, ...props }, ref) => {
    return (
      <div className={cn("ds-card", `ds-card--pad-${padding}`, className)} ref={ref} {...props}>
        {children}
      </div>
    );
  },
);

Card.displayName = "Card";

type CardHeaderProps = HTMLAttributes<HTMLDivElement> & {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  eyebrow?: string;
};

export function CardHeader({
  className,
  title,
  subtitle,
  actions,
  eyebrow,
  ...props
}: CardHeaderProps) {
  return (
    <div className={cn("ds-card__header", className)} {...props}>
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h2 className="ds-card__title">{title}</h2>
        {subtitle ? <p className="ds-card__subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="ds-card__actions">{actions}</div> : null}
    </div>
  );
}
