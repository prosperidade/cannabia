"use client";

import type { ExtractedCondition, ClinicalAnalysis } from "@/lib/types-medical";
import { Card, CardHeader, Badge } from "@/components/ui";
import { cn } from "@/lib/cn";

type DifferentialDiagnosisCardProps = {
  conditions: ExtractedCondition[];
  analysis: ClinicalAnalysis;
  className?: string;
};

const confidenceTone = {
  alto: "success",
  medio: "warning",
  baixo: "danger",
} as const;

const confidenceLabel = {
  alto: "Alta",
  medio: "Media",
  baixo: "Baixa",
} as const;

export function DifferentialDiagnosisCard({
  conditions,
  analysis,
  className,
}: DifferentialDiagnosisCardProps) {
  const allConditions = [
    ...conditions.map((c) => ({
      name: c.condition_name,
      icd10: c.icd10_hint,
      confidence: c.confidence,
      evidence: c.evidence_snippet,
      source: "ia" as const,
    })),
    ...analysis.probable_conditions
      .filter((pc) => !conditions.some((c) => c.condition_name.toLowerCase() === pc.toLowerCase()))
      .map((pc) => ({
        name: pc,
        icd10: null as string | null,
        confidence: "medio" as const,
        evidence: null as string | null,
        source: "pipeline" as const,
      })),
  ];

  return (
    <Card className={cn("ds-ddx", className)}>
      <CardHeader
        title="Diagnosticos Diferenciais"
        subtitle="Sugeridos pela IA com base na anamnese"
        eyebrow="INTELIGENCIA CLINICA"
        actions={
          <Badge tone="info" pulse>
            {allConditions.length} hipotese{allConditions.length !== 1 ? "s" : ""}
          </Badge>
        }
      />

      {analysis.red_flags.length > 0 ? (
        <div className="ds-ddx__flags">
          <span className="ds-ddx__flags-icon" aria-hidden="true">
            &#9888;
          </span>
          <div>
            <strong className="ds-ddx__flags-title">Red Flags Identificadas</strong>
            <ul className="ds-ddx__flags-list">
              {analysis.red_flags.map((flag) => (
                <li key={flag}>{flag}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      <div className="ds-ddx__list">
        {allConditions.map((cond, i) => (
          <div key={`${cond.name}-${i}`} className="ds-ddx__item">
            <div className="ds-ddx__item-header">
              <span className="ds-ddx__item-rank">{i + 1}</span>
              <div className="ds-ddx__item-body">
                <strong className="ds-ddx__item-name">{cond.name}</strong>
                {cond.icd10 ? <span className="ds-ddx__item-icd">CID-10: {cond.icd10}</span> : null}
              </div>
              <Badge tone={confidenceTone[cond.confidence]}>
                {confidenceLabel[cond.confidence]}
              </Badge>
            </div>
            {cond.evidence ? (
              <blockquote className="ds-ddx__item-evidence">
                &ldquo;{cond.evidence}&rdquo;
              </blockquote>
            ) : null}
          </div>
        ))}
      </div>

      {analysis.recommended_exams.length > 0 ? (
        <div className="ds-ddx__exams">
          <h3 className="ds-ddx__exams-title">Exames Recomendados</h3>
          <div className="ds-ddx__exams-chips">
            {analysis.recommended_exams.map((exam) => (
              <span key={exam} className="ds-ddx__exam-chip">
                {exam}
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}
