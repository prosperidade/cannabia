"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { getAttendance, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceDetail, TimelineEvent, MedicalRecordEntry } from "@/lib/types";
import type {
  RiskLevel,
  ClinicalAnalysis,
  TreatmentPlan,
  VitalSigns,
  PatientContext,
} from "@/lib/types-medical";
import {
  MaterialIcon,
  Badge,
  Button,
  Card,
  Avatar,
  StatCard,
  ProgressBar,
} from "@/components/ui-tw";

/* ---------------------------------------------------------------------------
 * Types & helpers
 * --------------------------------------------------------------------------- */

const RISK_CONFIG: Record<
  RiskLevel,
  { label: string; tone: "danger" | "warning" | "info" | "primary" }
> = {
  critico: { label: "Critico", tone: "danger" },
  alto: { label: "Alto", tone: "warning" },
  moderado: { label: "Moderado", tone: "info" },
  baixo: { label: "Baixo", tone: "primary" },
};

const EVENT_TYPE_CONFIG: Record<string, { icon: string; color: string; dotColor: string }> = {
  consultation: {
    icon: "stethoscope",
    color: "text-primary",
    dotColor: "bg-primary",
  },
  prescription: {
    icon: "prescriptions",
    color: "text-emerald-400",
    dotColor: "bg-emerald-500",
  },
  note: {
    icon: "edit_note",
    color: "text-blue-400",
    dotColor: "bg-blue-500",
  },
  exam: {
    icon: "biotech",
    color: "text-amber-400",
    dotColor: "bg-amber-500",
  },
  report: {
    icon: "description",
    color: "text-purple-400",
    dotColor: "bg-purple-500",
  },
  default: {
    icon: "event",
    color: "text-stone-400",
    dotColor: "bg-stone-500",
  },
};

function getEventConfig(eventType: string) {
  return EVENT_TYPE_CONFIG[eventType] ?? EVENT_TYPE_CONFIG.default;
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatDateShort(iso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/* ---------------------------------------------------------------------------
 * Data extraction helpers — dados reais da API, sem fallbacks mock
 * --------------------------------------------------------------------------- */

function derivePatientContext(detail: AttendanceDetail): PatientContext {
  const anamnesis = detail.report.anamnesis_data ?? {};
  return {
    id: detail.report.patient_id ?? 0,
    name: detail.report.patient_name,
    age: (anamnesis.age as number | undefined) ?? 0,
    main_complaint:
      (anamnesis.main_complaint as string | undefined) ??
      (anamnesis.queixa_principal as string | undefined) ??
      "",
    symptoms:
      (anamnesis.symptoms as string[] | undefined) ??
      (anamnesis.sintomas as string[] | undefined) ??
      [],
    current_medications:
      (anamnesis.current_medications as string[] | undefined) ??
      (anamnesis.medicamentos_atuais as string[] | undefined) ??
      [],
    allergies:
      (anamnesis.allergies as string[] | undefined) ??
      (anamnesis.alergias as string[] | undefined) ??
      [],
    medical_history:
      (anamnesis.medical_history as string | undefined) ??
      (anamnesis.historico_medico as string | undefined) ??
      null,
  };
}

function deriveClinicalAnalysis(detail: AttendanceDetail): ClinicalAnalysis {
  const ca = detail.report.clinical_analysis ?? {};
  const rawRisk = ((ca.risk_level as string | undefined) ?? "").toLowerCase().trim();
  let riskLevel: RiskLevel = "baixo";
  if (rawRisk === "critical" || rawRisk === "critico") riskLevel = "critico";
  else if (rawRisk === "high" || rawRisk === "alto") riskLevel = "alto";
  else if (rawRisk === "moderate" || rawRisk === "moderado") riskLevel = "moderado";

  return {
    probable_conditions: (ca.probable_conditions as string[] | undefined) ?? [],
    risk_level: riskLevel,
    recommended_exams: (ca.recommended_exams as string[] | undefined) ?? [],
    red_flags: (ca.red_flags as string[] | undefined) ?? [],
  };
}

function deriveTreatmentPlan(detail: AttendanceDetail): TreatmentPlan {
  const tp = detail.report.treatment_plan ?? {};
  return {
    cannabinoid_ratio:
      (tp.cannabinoid_ratio as string | undefined) ??
      (tp.proporcao_canabinoides as string | undefined) ??
      "",
    suggested_dosage:
      (tp.suggested_dosage as string | undefined) ??
      (tp.dosagem_sugerida as string | undefined) ??
      "",
    administration_route:
      (tp.administration_route as string | undefined) ??
      (tp.via_administracao as string | undefined) ??
      "",
    monitoring_plan:
      (tp.monitoring_plan as string | undefined) ??
      (tp.plano_monitoramento as string | undefined) ??
      "",
    precautions:
      (tp.precautions as string[] | undefined) ?? (tp.precaucoes as string[] | undefined) ?? [],
  };
}

function deriveVitals(detail: AttendanceDetail): VitalSigns | null {
  const anamnesis = detail.report.anamnesis_data ?? {};
  const vitals = (anamnesis.vital_signs ?? anamnesis.sinais_vitais) as
    | Partial<VitalSigns>
    | undefined;
  if (!vitals) return null;
  return {
    bp_systolic: vitals.bp_systolic ?? null,
    bp_diastolic: vitals.bp_diastolic ?? null,
    heart_rate: vitals.heart_rate ?? null,
    temperature: vitals.temperature ?? null,
    spo2: vitals.spo2 ?? null,
    respiratory_rate: vitals.respiratory_rate ?? null,
    weight_kg: vitals.weight_kg ?? null,
    height_cm: vitals.height_cm ?? null,
    bmi: vitals.bmi ?? null,
    pain_level: vitals.pain_level ?? null,
  };
}

/* ---------------------------------------------------------------------------
 * Sub-components
 * --------------------------------------------------------------------------- */

function PatientHeader({
  patient,
  riskLevel,
  phone,
  createdAt,
}: {
  patient: PatientContext;
  riskLevel: RiskLevel;
  phone: string;
  createdAt: string;
}) {
  const risk = RISK_CONFIG[riskLevel];

  return (
    <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
      <div className="flex items-center gap-5 md:gap-8">
        <div className="relative">
          <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full" />
          <Avatar
            name={patient.name}
            size="lg"
            className="relative !w-20 !h-20 md:!w-28 md:!h-28 !rounded-2xl border-2 border-primary/20 shadow-2xl"
          />
          <Badge tone={risk.tone} className="absolute -bottom-2 -right-2 shadow-lg">
            {risk.label}
          </Badge>
        </div>
        <div className="space-y-1">
          <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
            <h2 className="text-2xl md:text-4xl font-bold font-headline tracking-tighter text-on-surface">
              {patient.name}
            </h2>
            <span className="text-primary/60 font-mono text-sm md:text-lg">
              #{patient.id || "---"}
            </span>
          </div>
          <div className="flex flex-wrap gap-3 md:gap-6 text-stone-400 text-xs md:text-sm">
            {patient.age > 0 && (
              <span className="flex items-center gap-1">
                <MaterialIcon icon="calendar_today" size="sm" />
                {patient.age} anos
              </span>
            )}
            <span className="flex items-center gap-1">
              <MaterialIcon icon="phone" size="sm" />
              {phone}
            </span>
            <span className="flex items-center gap-1">
              <MaterialIcon icon="event" size="sm" />
              Desde {formatDateShort(createdAt)}
            </span>
          </div>
          {patient.main_complaint && (
            <p className="text-xs md:text-sm text-stone-500 italic mt-1">
              Queixa: {patient.main_complaint}
            </p>
          )}
        </div>
      </div>
      <div className="flex gap-3 w-full md:w-auto">
        <Link
          href="#"
          className="flex-1 md:flex-none px-5 py-2.5 rounded-lg border border-white/10 hover:bg-white/5 transition-all flex items-center justify-center gap-2 text-xs md:text-sm font-medium"
        >
          <MaterialIcon icon="edit" size="sm" />
          Editar Perfil
        </Link>
        <Link
          href="#"
          className="flex-1 md:flex-none px-5 py-2.5 rounded-lg bg-primary text-on-primary hover:opacity-90 transition-all flex items-center justify-center gap-2 text-xs md:text-sm font-bold shadow-lg shadow-primary/10"
        >
          <MaterialIcon icon="print" size="sm" />
          Exportar
        </Link>
      </div>
    </div>
  );
}

function QuickStatsRow({
  totalConsultations,
  lastVisit,
  treatmentDuration,
  complianceScore,
}: {
  totalConsultations: number;
  lastVisit: string;
  treatmentDuration: string | null;
  complianceScore: number | null;
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6">
      <StatCard icon="event_available" label="Consultas" value={totalConsultations} />
      <StatCard icon="schedule" label="Ultima Visita" value={lastVisit} />
      <StatCard icon="timer" label="Em Tratamento" value={treatmentDuration ?? "--"} />
      <StatCard
        icon="verified"
        label="Adesao"
        value={complianceScore !== null ? `${complianceScore}%` : "--"}
        delta={complianceScore !== null ? (complianceScore >= 80 ? "Boa" : "Atencao") : undefined}
        deltaType={complianceScore !== null ? (complianceScore >= 80 ? "up" : "down") : "neutral"}
      />
    </div>
  );
}

function PatientContextCard({
  patient,
  clinicalAnalysis,
}: {
  patient: PatientContext;
  clinicalAnalysis: ClinicalAnalysis;
}) {
  return (
    <Card variant="glass" padding="lg" className="rounded-3xl space-y-6">
      <div className="flex items-center gap-2">
        <MaterialIcon icon="person_search" className="text-primary" />
        <h3 className="text-lg font-bold font-headline text-on-surface">Contexto do Paciente</h3>
      </div>

      {/* Symptoms */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em]">
          Sintomas
        </h4>
        <div className="flex flex-wrap gap-2">
          {patient.symptoms.map((s) => (
            <span
              key={s}
              className="px-3 py-1.5 bg-primary/10 border border-primary/20 rounded-lg text-xs text-primary font-medium"
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Allergies */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em]">
          Alergias
        </h4>
        <div className="flex flex-wrap gap-2">
          {patient.allergies.map((a) => (
            <span
              key={a}
              className="px-3 py-1.5 bg-error/10 border border-error/20 rounded-lg text-xs text-error font-medium"
            >
              {a}
            </span>
          ))}
        </div>
      </div>

      {/* Current Medications */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em]">
          Medicamentos Atuais
        </h4>
        <div className="flex flex-wrap gap-2">
          {patient.current_medications.map((m) => (
            <span
              key={m}
              className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-stone-300"
            >
              {m}
            </span>
          ))}
        </div>
      </div>

      {/* Medical History */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em]">
          Historico Medico
        </h4>
        <p className="text-sm text-stone-400 leading-relaxed">
          {patient.medical_history ?? "Sem historico registrado."}
        </p>
      </div>

      {/* Red Flags */}
      {clinicalAnalysis.red_flags.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-[10px] font-black text-error uppercase tracking-[0.2em]">
            Alertas Clinicos
          </h4>
          <div className="space-y-1">
            {clinicalAnalysis.red_flags.map((f) => (
              <div key={f} className="flex items-start gap-2 text-sm text-error/90">
                <MaterialIcon icon="warning" size="sm" className="text-error mt-0.5" />
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Probable Conditions */}
      <div className="space-y-2">
        <h4 className="text-[10px] font-black text-stone-400 uppercase tracking-[0.2em]">
          Condicoes Provaveis
        </h4>
        <div className="flex flex-wrap gap-2">
          {clinicalAnalysis.probable_conditions.map((c) => (
            <span
              key={c}
              className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-400 font-medium"
            >
              {c}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}

function ClinicalTimeline({
  timeline,
  medicalEntries,
}: {
  timeline: TimelineEvent[];
  medicalEntries: MedicalRecordEntry[];
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Combine timeline events and medical record entries into a sorted list
  type UnifiedEvent = {
    id: number;
    type: string;
    title: string;
    description: string | null;
    date: string;
    tags: string[];
    source: "timeline" | "medical";
  };

  const allEvents: UnifiedEvent[] = [
    ...timeline.map((e) => ({
      id: e.id,
      type: e.event_type,
      title: e.title,
      description: e.description,
      date: e.event_time,
      tags: [e.journey_stage, e.source_type].filter(Boolean) as string[],
      source: "timeline" as const,
    })),
    ...medicalEntries.map((e) => ({
      id: e.id + 100000,
      type: e.entry_type,
      title: e.title,
      description: e.medical_observations,
      date: e.created_at,
      tags: [e.entry_type, e.status].filter(Boolean),
      source: "medical" as const,
    })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  if (allEvents.length === 0) {
    return (
      <Card variant="glass" padding="lg" className="rounded-3xl">
        <div className="flex items-center gap-2 mb-4">
          <MaterialIcon icon="timeline" className="text-primary" />
          <h3 className="text-lg font-bold font-headline text-on-surface">Historico Clinico</h3>
        </div>
        <p className="text-sm text-stone-500 italic">Nenhum evento registrado ainda.</p>
      </Card>
    );
  }

  return (
    <Card variant="glass" padding="lg" className="rounded-3xl">
      <div className="flex items-center gap-2 mb-6">
        <MaterialIcon icon="timeline" className="text-primary" />
        <h3 className="text-lg font-bold font-headline text-on-surface">Historico Clinico</h3>
        <Badge tone="neutral" className="ml-auto">
          {allEvents.length} eventos
        </Badge>
      </div>

      <div className="relative space-y-6 before:content-[''] before:absolute before:left-3 before:top-2 before:bottom-2 before:w-[2px] before:bg-white/5">
        {allEvents.map((event, i) => {
          const config = getEventConfig(event.type);
          const isExpanded = expandedId === event.id;
          const opacity = i === 0 ? "" : i === 1 ? "opacity-80" : "opacity-60";

          return (
            <div
              key={event.id}
              className={cn("relative pl-10 cursor-pointer", opacity)}
              onClick={() => setExpandedId(isExpanded ? null : event.id)}
            >
              <div
                className={cn(
                  "absolute left-0 top-1 w-6 h-6 rounded-full border-4 border-surface flex items-center justify-center",
                  config.dotColor,
                )}
              >
                <MaterialIcon
                  icon={config.icon}
                  size="sm"
                  className={cn("text-white text-[10px]")}
                />
              </div>

              <p className="text-[10px] font-bold text-stone-500 uppercase tracking-widest">
                {formatDate(event.date)}
              </p>
              <h4 className="text-on-surface font-bold mt-1 text-sm">{event.title}</h4>

              {event.description && (
                <p
                  className={cn(
                    "text-sm text-stone-400 mt-1 leading-relaxed",
                    !isExpanded && "line-clamp-2",
                  )}
                >
                  {event.description}
                </p>
              )}

              {event.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {event.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 bg-white/5 border border-white/10 rounded-full text-[10px] text-stone-400"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {isExpanded && (
                <div className="mt-2 text-xs text-stone-500 flex items-center gap-1">
                  <MaterialIcon icon="info" size="sm" />
                  Fonte: {event.source === "timeline" ? "Timeline" : "Prontuario"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function VitalSignsCard({ vitals }: { vitals: VitalSigns }) {
  const items = [
    {
      label: "PA",
      value:
        vitals.bp_systolic && vitals.bp_diastolic
          ? `${vitals.bp_systolic}/${vitals.bp_diastolic}`
          : "--",
      unit: "mmHg",
      icon: "monitor_heart",
      trend: "stable" as const,
    },
    {
      label: "FC",
      value: vitals.heart_rate ?? "--",
      unit: "bpm",
      icon: "favorite",
      trend: "stable" as const,
    },
    {
      label: "Temp",
      value: vitals.temperature ?? "--",
      unit: "C",
      icon: "thermostat",
      trend: "stable" as const,
    },
    {
      label: "SpO2",
      value: vitals.spo2 ?? "--",
      unit: "%",
      icon: "pulmonology",
      trend: "stable" as const,
    },
    {
      label: "IMC",
      value: vitals.bmi ?? "--",
      unit: "kg/m2",
      icon: "monitor_weight",
      trend: "stable" as const,
    },
    {
      label: "Dor",
      value: vitals.pain_level ?? "--",
      unit: "/10",
      icon: "sentiment_dissatisfied",
      trend: (vitals.pain_level ?? 0) > 5 ? ("up" as const) : ("stable" as const),
    },
  ];

  return (
    <Card variant="glass" padding="lg" className="rounded-3xl">
      <div className="flex items-center gap-2 mb-5">
        <MaterialIcon icon="vital_signs" className="text-primary" filled />
        <h3 className="text-lg font-bold font-headline text-on-surface">Sinais Vitais</h3>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5"
          >
            <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
              <MaterialIcon icon={item.icon} size="sm" className="text-primary" />
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-stone-500 font-bold">
                {item.label}
              </p>
              <p className="text-base font-bold text-on-surface font-headline">
                {item.value} <span className="text-xs font-normal text-stone-500">{item.unit}</span>
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function TreatmentPlanCard({ plan }: { plan: TreatmentPlan }) {
  return (
    <div className="bg-primary p-[2px] rounded-3xl">
      <div className="bg-surface-container-lowest p-6 rounded-[calc(1.5rem-2px)] space-y-5">
        <div className="flex justify-between items-start">
          <div>
            <h3 className="text-lg font-bold font-headline text-on-surface">
              Plano Terapeutico Ativo
            </h3>
            <p className="text-primary text-xs font-bold mt-1">Tratamento Canabico</p>
          </div>
          <MaterialIcon icon="potted_plant" className="text-primary" size="lg" />
        </div>

        <div className="p-4 rounded-xl bg-white/5 border border-white/5 space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-stone-500">Proporcao</span>
            <span className="text-on-surface font-bold">{plan.cannabinoid_ratio}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-stone-500">Dosagem</span>
            <span className="text-on-surface font-medium">{plan.suggested_dosage}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-stone-500">Via</span>
            <span className="text-on-surface font-medium">{plan.administration_route}</span>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
            Monitoramento
          </h4>
          <p className="text-sm text-stone-400 leading-relaxed">{plan.monitoring_plan}</p>
        </div>

        {plan.precautions.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-[10px] font-black text-amber-500 uppercase tracking-widest">
              Precaucoes
            </h4>
            {plan.precautions.map((p) => (
              <div key={p} className="flex items-start gap-2 text-xs text-amber-400">
                <MaterialIcon icon="warning" size="sm" className="text-amber-500 mt-0.5" />
                {p}
              </div>
            ))}
          </div>
        )}

        {/* TODO: Replace with real treatment progress from API */}
        <div className="space-y-2">
          <div className="flex justify-between items-end">
            <span className="text-[10px] font-bold text-stone-500 uppercase">
              Progresso do Tratamento
            </span>
            <span className="text-on-surface font-bold text-sm">
              12 / 30 <span className="text-xs text-stone-500 font-normal">dias</span>
            </span>
          </div>
          <ProgressBar value={40} variant="primary" size="sm" glow />
        </div>
      </div>
    </div>
  );
}

function SymptomEvolutionCard() {
  return (
    <Card variant="glass" padding="lg" className="rounded-3xl">
      <div className="flex items-center gap-2 mb-5">
        <MaterialIcon icon="trending_down" className="text-primary" />
        <h3 className="text-lg font-bold font-headline text-on-surface">Evolucao dos Sintomas</h3>
      </div>
      <div className="flex flex-col items-center justify-center py-6 text-center">
        <MaterialIcon icon="show_chart" size="xl" className="text-stone-600 mb-3" />
        <p className="text-sm text-stone-400">
          Dados de evolucao serao exibidos apos registros longitudinais do paciente.
        </p>
      </div>
    </Card>
  );
}

function MedicalNotesCard({
  entries,
  attendanceId,
}: {
  entries: MedicalRecordEntry[];
  attendanceId: string;
}) {
  const sortedEntries = [...entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <Card variant="glass" padding="lg" className="rounded-3xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MaterialIcon icon="edit_note" className="text-primary" />
          <h3 className="text-lg font-bold font-headline text-on-surface">Notas Medicas</h3>
        </div>
        <Link href={`/med/prontuario/${attendanceId}/notas`}>
          <Button variant="secondary" size="sm" icon="add">
            Adicionar Nota
          </Button>
        </Link>
      </div>

      {sortedEntries.length === 0 ? (
        <p className="text-sm text-stone-500 italic">Nenhuma nota medica registrada.</p>
      ) : (
        <div className="space-y-3">
          {sortedEntries.slice(0, 5).map((entry) => (
            <div
              key={entry.id}
              className="p-4 rounded-xl bg-black/20 border border-white/5 space-y-2"
            >
              <div className="flex justify-between items-start">
                <h4 className="text-sm font-bold text-on-surface">{entry.title}</h4>
                <span className="text-[10px] text-stone-500 font-medium whitespace-nowrap ml-2">
                  {formatDate(entry.created_at)}
                </span>
              </div>
              {entry.medical_observations && (
                <p className="text-sm text-stone-400 italic leading-relaxed line-clamp-3">
                  {entry.medical_observations}
                </p>
              )}
              <div className="flex items-center gap-3 text-[10px] text-stone-500">
                {entry.author_name && (
                  <span className="flex items-center gap-1">
                    <MaterialIcon icon="person" size="sm" />
                    {entry.author_name}
                  </span>
                )}
                <Badge tone="neutral">{entry.status}</Badge>
              </div>
            </div>
          ))}
          {sortedEntries.length > 5 && (
            <Link
              href={`/med/prontuario/${attendanceId}/notas`}
              className="block text-center text-xs text-primary hover:underline py-2"
            >
              Ver todas as {sortedEntries.length} notas
            </Link>
          )}
        </div>
      )}
    </Card>
  );
}

/* ---------------------------------------------------------------------------
 * Main Page Component
 * --------------------------------------------------------------------------- */

export default function ProntuarioPage() {
  const params = useParams();
  const router = useRouter();
  useApiSession();
  const id = params.id as string;

  const [detail, setDetail] = useState<AttendanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAttendance(id);
      setDetail(data);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha ao carregar prontuario.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  /* ---- Loading state ---- */
  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando prontuario...</p>
        </div>
      </div>
    );
  }

  /* ---- Error state ---- */
  if (error || !detail) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card variant="glass" padding="lg" className="max-w-md text-center">
          <MaterialIcon icon="error_outline" size="xl" className="text-error mb-4" />
          <h3 className="text-lg font-bold text-on-surface mb-2">Erro ao Carregar</h3>
          <p className="text-sm text-stone-400 mb-4">{error ?? "Prontuario nao encontrado."}</p>
          <div className="flex justify-center gap-3">
            <Button variant="secondary" size="sm" icon="arrow_back" onClick={() => router.back()}>
              Voltar
            </Button>
            <Button variant="primary" size="sm" icon="refresh" onClick={() => void loadData()}>
              Tentar Novamente
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  /* ---- Derived data ---- */
  const patient = derivePatientContext(detail);
  const clinicalAnalysis = deriveClinicalAnalysis(detail);
  const treatmentPlan = deriveTreatmentPlan(detail);
  const vitals = deriveVitals(detail);

  const totalConsultations =
    detail.timeline.filter((e) => e.event_type === "consultation").length +
    detail.medical_record_entries.length;
  const lastVisitDate =
    detail.timeline.length > 0
      ? formatDateShort(detail.timeline[0].event_time)
      : formatDateShort(detail.report.created_at);

  // Treatment duration: from first timeline event to now
  const treatmentDuration = (() => {
    if (detail.timeline.length === 0) return null;
    const firstEvent = detail.timeline[detail.timeline.length - 1];
    const diffMs = Date.now() - new Date(firstEvent.event_time).getTime();
    const diffDays = Math.floor(diffMs / 86_400_000);
    if (diffDays < 7) return `${diffDays} dias`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} semanas`;
    return `${Math.floor(diffDays / 30)} meses`;
  })();

  // Compliance: entries completed / total consultations
  const complianceScore =
    totalConsultations > 0
      ? Math.round((detail.medical_record_entries.length / Math.max(totalConsultations, 1)) * 100)
      : null;

  return (
    <section className="space-y-6 md:space-y-8 pb-8">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-stone-500">
        <Link href="/med/atendimentos" className="hover:text-primary transition-colors">
          Atendimentos
        </Link>
        <MaterialIcon icon="chevron_right" size="sm" />
        <span className="text-on-surface font-medium">Prontuario #{id}</span>
      </div>

      {/* Patient Header */}
      <PatientHeader
        patient={patient}
        riskLevel={clinicalAnalysis.risk_level}
        phone={detail.report.phone}
        createdAt={detail.report.created_at}
      />

      {/* Quick Stats */}
      <QuickStatsRow
        totalConsultations={totalConsultations || 1}
        lastVisit={lastVisitDate}
        treatmentDuration={treatmentDuration}
        complianceScore={complianceScore}
      />

      {/* Main Grid: Left + Right columns */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column */}
        <div className="lg:col-span-8 space-y-6">
          <PatientContextCard patient={patient} clinicalAnalysis={clinicalAnalysis} />
          <ClinicalTimeline
            timeline={detail.timeline}
            medicalEntries={detail.medical_record_entries}
          />
        </div>

        {/* Right Column */}
        <div className="lg:col-span-4 space-y-6">
          {vitals && <VitalSignsCard vitals={vitals} />}
          <TreatmentPlanCard plan={treatmentPlan} />
          <SymptomEvolutionCard />
          <MedicalNotesCard entries={detail.medical_record_entries} attendanceId={id} />
        </div>
      </div>
    </section>
  );
}
