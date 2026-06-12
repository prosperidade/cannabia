"use client";

import { useCallback, useState } from "react";
import type {
  PrescriptionData,
  PrescriptionItem,
  PrescriptionType,
  TreatmentPlan,
  PatientContext,
} from "@/lib/types-medical";
import { Card, CardHeader, Badge, Button, Input } from "@/components/ui";
import { cn } from "@/lib/cn";

type PrescriptionFormProps = {
  patient: PatientContext;
  plan: TreatmentPlan;
  prescriberName?: string;
  prescriberCrm?: string;
  prescriberUf?: string;
  className?: string;
  onSubmit?: (data: PrescriptionData) => void;
};

function defaultItem(plan: TreatmentPlan): PrescriptionItem {
  return {
    medication: `Cannabis medicinal (${plan.cannabinoid_ratio})`,
    concentration: "",
    dosage: plan.suggested_dosage,
    route: plan.administration_route,
    frequency: "",
    duration: "",
    instructions: "",
  };
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function PrescriptionForm({
  patient,
  plan,
  prescriberName = "",
  prescriberCrm = "",
  prescriberUf = "",
  className,
  onSubmit,
}: PrescriptionFormProps) {
  const [rxType, setRxType] = useState<PrescriptionType>("branca");
  const [items, setItems] = useState<PrescriptionItem[]>([defaultItem(plan)]);
  const [notes, setNotes] = useState("");
  const [prescriber, setPrescriber] = useState({
    name: prescriberName,
    crm: prescriberCrm,
    uf: prescriberUf,
  });
  const [patientCpf, setPatientCpf] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const updateItem = useCallback((index: number, field: keyof PrescriptionItem, value: string) => {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, [field]: value } : it)));
  }, []);

  const addItem = useCallback(() => {
    setItems((prev) => [...prev, defaultItem(plan)]);
  }, [plan]);

  const removeItem = useCallback((index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);

    const data: PrescriptionData = {
      type: rxType,
      patient_name: patient.name,
      patient_cpf: patientCpf,
      prescriber_name: prescriber.name,
      prescriber_crm: prescriber.crm,
      prescriber_uf: prescriber.uf,
      date: today(),
      items,
      notes,
    };

    onSubmit?.(data);
    setSubmitting(false);
  }

  return (
    <Card className={cn("ds-rx", className)}>
      <CardHeader
        title="Prescricao Eletronica"
        subtitle="Receita semi-preenchida pela IA"
        eyebrow="ANVISA"
        actions={
          <Badge tone={rxType === "azul" ? "info" : "neutral"}>
            Receita {rxType === "azul" ? "Azul (B1)" : "Branca (C1)"}
          </Badge>
        }
      />

      {/* Type Selector */}
      <div className="ds-rx__type-toggle">
        <button
          type="button"
          className={cn("ds-rx__type-btn", rxType === "branca" && "ds-rx__type-btn--active")}
          onClick={() => setRxType("branca")}
        >
          <span className="ds-rx__type-dot ds-rx__type-dot--branca" />
          Receita Branca (C1)
        </button>
        <button
          type="button"
          className={cn(
            "ds-rx__type-btn",
            rxType === "azul" && "ds-rx__type-btn--active ds-rx__type-btn--azul",
          )}
          onClick={() => setRxType("azul")}
        >
          <span className="ds-rx__type-dot ds-rx__type-dot--azul" />
          Receita Azul (B1)
        </button>
      </div>

      <form className="ds-rx__form" onSubmit={handleSubmit}>
        {/* Header - Prescriber & Patient */}
        <fieldset className="ds-rx__fieldset">
          <legend className="ds-rx__legend">Identificacao</legend>
          <div className="ds-rx__row ds-rx__row--3col">
            <Input
              label="Prescritor"
              value={prescriber.name}
              onChange={(e) => setPrescriber((p) => ({ ...p, name: e.target.value }))}
              placeholder="Dr. Nome Completo"
            />
            <Input
              label="CRM"
              value={prescriber.crm}
              onChange={(e) => setPrescriber((p) => ({ ...p, crm: e.target.value }))}
              placeholder="000000"
            />
            <Input
              label="UF"
              value={prescriber.uf}
              onChange={(e) => setPrescriber((p) => ({ ...p, uf: e.target.value }))}
              placeholder="SP"
              maxLength={2}
            />
          </div>
          <div className="ds-rx__row ds-rx__row--2col">
            <Input label="Paciente" value={patient.name} readOnly />
            <Input
              label="CPF do Paciente"
              value={patientCpf}
              onChange={(e) => setPatientCpf(e.target.value)}
              placeholder="000.000.000-00"
            />
          </div>
        </fieldset>

        {/* Medication Items */}
        <fieldset className="ds-rx__fieldset">
          <legend className="ds-rx__legend">Medicamentos</legend>
          {items.map((item, idx) => (
            <div key={idx} className="ds-rx__med-block">
              <div className="ds-rx__med-header">
                <span className="ds-rx__med-num">{idx + 1}</span>
                {items.length > 1 ? (
                  <button
                    type="button"
                    className="ds-rx__med-remove"
                    onClick={() => removeItem(idx)}
                    aria-label={`Remover medicamento ${idx + 1}`}
                  >
                    &#x2715;
                  </button>
                ) : null}
              </div>
              <div className="ds-rx__row ds-rx__row--2col">
                <Input
                  label="Medicamento"
                  value={item.medication}
                  onChange={(e) => updateItem(idx, "medication", e.target.value)}
                />
                <Input
                  label="Concentracao"
                  value={item.concentration}
                  onChange={(e) => updateItem(idx, "concentration", e.target.value)}
                  placeholder="ex: 200mg/mL"
                />
              </div>
              <div className="ds-rx__row ds-rx__row--3col">
                <Input
                  label="Dosagem"
                  value={item.dosage}
                  onChange={(e) => updateItem(idx, "dosage", e.target.value)}
                />
                <Input
                  label="Via"
                  value={item.route}
                  onChange={(e) => updateItem(idx, "route", e.target.value)}
                />
                <Input
                  label="Frequencia"
                  value={item.frequency}
                  onChange={(e) => updateItem(idx, "frequency", e.target.value)}
                  placeholder="ex: 12/12h"
                />
              </div>
              <div className="ds-rx__row ds-rx__row--2col">
                <Input
                  label="Duracao"
                  value={item.duration}
                  onChange={(e) => updateItem(idx, "duration", e.target.value)}
                  placeholder="ex: 30 dias"
                />
                <Input
                  label="Instrucoes"
                  value={item.instructions}
                  onChange={(e) => updateItem(idx, "instructions", e.target.value)}
                  placeholder="Tomar antes de dormir"
                />
              </div>
            </div>
          ))}

          <Button variant="ghost" size="sm" onClick={addItem} type="button">
            + Adicionar Medicamento
          </Button>
        </fieldset>

        {/* Notes */}
        <fieldset className="ds-rx__fieldset">
          <legend className="ds-rx__legend">Observacoes</legend>
          <div className="ds-field">
            <textarea
              className="ds-field__input ds-rx__textarea"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="Observacoes adicionais para o farmaceutico..."
            />
          </div>
        </fieldset>

        {/* Actions */}
        <div className="ds-rx__actions">
          <Button variant="secondary" type="button">
            Visualizar PDF
          </Button>
          <Button variant="primary" type="submit" loading={submitting}>
            Assinar e Emitir Receita
          </Button>
        </div>
      </form>
    </Card>
  );
}
