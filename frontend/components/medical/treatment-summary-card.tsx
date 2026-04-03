"use client";

import type { TreatmentPlan, ScientificReport } from "@/lib/types-medical";
import { Card, CardHeader, Badge } from "@/components/ui";
import { cn } from "@/lib/cn";

type TreatmentSummaryCardProps = {
  plan: TreatmentPlan;
  report: ScientificReport;
  className?: string;
};

export function TreatmentSummaryCard({ plan, report, className }: TreatmentSummaryCardProps) {
  return (
    <Card className={cn("ds-treatment", className)}>
      <CardHeader
        title="Plano Terapeutico"
        subtitle="Sugestao canabinoides gerada pela IA"
        eyebrow="TRATAMENTO"
        actions={<Badge tone="success">Gerado</Badge>}
      />

      <div className="ds-treatment__grid">
        <div className="ds-treatment__block">
          <span className="ds-treatment__block-icon" aria-hidden="true">&#x2696;</span>
          <div>
            <span className="ds-treatment__block-label">Ratio CBD:THC</span>
            <strong className="ds-treatment__block-value">{plan.cannabinoid_ratio}</strong>
          </div>
        </div>

        <div className="ds-treatment__block">
          <span className="ds-treatment__block-icon" aria-hidden="true">&#x1F48A;</span>
          <div>
            <span className="ds-treatment__block-label">Dosagem Sugerida</span>
            <strong className="ds-treatment__block-value">{plan.suggested_dosage}</strong>
          </div>
        </div>

        <div className="ds-treatment__block">
          <span className="ds-treatment__block-icon" aria-hidden="true">&#x1F489;</span>
          <div>
            <span className="ds-treatment__block-label">Via de Administracao</span>
            <strong className="ds-treatment__block-value">{plan.administration_route}</strong>
          </div>
        </div>
      </div>

      <div className="ds-treatment__monitoring">
        <h3 className="ds-treatment__section-title">Plano de Monitoramento</h3>
        <p className="ds-treatment__monitoring-text">{plan.monitoring_plan}</p>
      </div>

      {plan.precautions.length > 0 ? (
        <div className="ds-treatment__precautions">
          <h3 className="ds-treatment__section-title">Precaucoes</h3>
          <ul className="ds-treatment__precaution-list">
            {plan.precautions.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="ds-treatment__evidence">
        <h3 className="ds-treatment__section-title">Evidencia Cientifica</h3>
        <p className="ds-treatment__evidence-summary">{report.summary}</p>
        {report.references.length > 0 ? (
          <details className="ds-treatment__refs">
            <summary>{report.references.length} referencia{report.references.length !== 1 ? "s" : ""} cientifica{report.references.length !== 1 ? "s" : ""}</summary>
            <ol className="ds-treatment__ref-list">
              {report.references.map((ref, i) => (
                <li key={i}>{ref}</li>
              ))}
            </ol>
          </details>
        ) : null}
      </div>
    </Card>
  );
}
