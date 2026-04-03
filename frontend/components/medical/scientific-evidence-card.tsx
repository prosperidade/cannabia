"use client";

import type { ScientificReport } from "@/lib/types-medical";
import { Card, CardHeader, Badge } from "@/components/ui";
import { cn } from "@/lib/cn";

type ScientificEvidenceCardProps = {
  report: ScientificReport;
  ragChunksUsed: number;
  reportModel: string;
  className?: string;
};

export function ScientificEvidenceCard({ report, ragChunksUsed, reportModel, className }: ScientificEvidenceCardProps) {
  return (
    <Card className={cn("ds-evidence", className)}>
      <CardHeader
        title="Base Cientifica"
        subtitle="Evidencias RAG (PubMed / Cochrane)"
        eyebrow="LITERATURA"
        actions={
          <div className="ds-evidence__meta-badges">
            <Badge tone="info">{ragChunksUsed} chunks RAG</Badge>
            <Badge tone="neutral">{reportModel}</Badge>
          </div>
        }
      />

      <p className="ds-evidence__summary">{report.summary}</p>

      {report.supporting_evidence.length > 0 ? (
        <div className="ds-evidence__section">
          <h3 className="ds-evidence__section-title">Evidencias de Suporte</h3>
          <ul className="ds-evidence__list">
            {report.supporting_evidence.map((ev, i) => (
              <li key={i} className="ds-evidence__item">
                <span className="ds-evidence__bullet" aria-hidden="true">&#x25B6;</span>
                {ev}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {report.references.length > 0 ? (
        <div className="ds-evidence__section">
          <h3 className="ds-evidence__section-title">Referencias</h3>
          <ol className="ds-evidence__refs">
            {report.references.map((ref, i) => (
              <li key={i} className="ds-evidence__ref">{ref}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </Card>
  );
}
