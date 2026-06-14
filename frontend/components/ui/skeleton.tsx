import { cn } from "@/lib/cn";

type SkeletonProps = {
  className?: string;
  /** Width in CSS units */
  width?: string;
  /** Height in CSS units */
  height?: string;
  /** Render as circle */
  circle?: boolean;
  /** Number of lines to render (creates a stack) */
  lines?: number;
};

export function Skeleton({
  className,
  width,
  height = "18px",
  circle = false,
  lines,
}: SkeletonProps) {
  if (lines && lines > 1) {
    return (
      <div
        aria-busy="true"
        aria-label="Carregando conteúdo"
        className="ds-skeleton-stack"
        role="status"
      >
        <span className="sr-only">Carregando...</span>
        {Array.from({ length: lines }, (_, i) => (
          <span
            className={cn("ds-skeleton", className)}
            key={i}
            style={{
              width: i === lines - 1 ? "60%" : width,
              height,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <span
      aria-busy="true"
      aria-label="Carregando"
      className={cn("ds-skeleton", circle && "ds-skeleton--circle", className)}
      role="status"
      style={{
        width: circle ? height : width,
        height,
      }}
    >
      <span className="sr-only">Carregando...</span>
    </span>
  );
}

/** Full card skeleton with header + lines */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Carregando painel"
      className="ds-card ds-card--pad-md"
      role="status"
    >
      <div className="ds-card__header">
        <div>
          <Skeleton height="12px" width="80px" />
          <Skeleton height="22px" width="180px" />
        </div>
      </div>
      <Skeleton lines={lines} />
    </div>
  );
}

/** Table skeleton: rows of bars */
export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div
      aria-busy="true"
      aria-label="Carregando tabela"
      className="ds-table-skeleton"
      role="status"
    >
      <span className="sr-only">Carregando tabela...</span>
      {Array.from({ length: rows }, (_, r) => (
        <div className="ds-table-skeleton__row" key={r}>
          {Array.from({ length: cols }, (_, c) => (
            <Skeleton
              height="16px"
              key={c}
              width={c === 0 ? "40%" : `${50 + Math.round(Math.random() * 30)}%`}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
