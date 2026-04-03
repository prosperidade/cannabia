"use client";

import type { RiskLevel } from "@/lib/types-medical";
import { cn } from "@/lib/cn";

type RiskIndicatorProps = {
  level: RiskLevel;
  className?: string;
};

const config: Record<RiskLevel, { label: string; css: string; pct: number }> = {
  baixo: { label: "Baixo", css: "ds-risk--low", pct: 25 },
  moderado: { label: "Moderado", css: "ds-risk--moderate", pct: 50 },
  alto: { label: "Alto", css: "ds-risk--high", pct: 75 },
  critico: { label: "Critico", css: "ds-risk--critical", pct: 100 },
};

export function RiskIndicator({ level, className }: RiskIndicatorProps) {
  const { label, css, pct } = config[level] ?? config.moderado;

  return (
    <div className={cn("ds-risk", css, className)} role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Nivel de risco: ${label}`}>
      <div className="ds-risk__track">
        <div className="ds-risk__fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="ds-risk__label">{label}</span>
    </div>
  );
}
