"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getPatientProfile, getPatientEvolution } from "@/lib/api";
import { Card, Badge, MaterialIcon, ProgressBar } from "@/components/ui-tw";

const QUICK_ACTIONS = [
  { label: "Meu Tratamento", icon: "medication", href: "/p/tratamento", color: "text-secondary" },
  { label: "Diario de Sintomas", icon: "edit_note", href: "/p/diario", color: "text-tertiary" },
  { label: "Falar com Medico", icon: "chat", href: "/p/consultas", color: "text-primary" },
];

const MOOD_OPTIONS = [
  { emoji: "\uD83E\uDD29", label: "Otimo" },
  { emoji: "\uD83D\uDE42", label: "Bem" },
  { emoji: "\uD83D\uDE10", label: "Neutro" },
  { emoji: "\uD83D\uDE15", label: "Baixo" },
  { emoji: "\uD83D\uDE16", label: "Mal" },
];

function getEvolutionVariant(value: number): "primary" | "success" | "warning" | "danger" {
  if (value >= 70) return "success";
  if (value >= 40) return "warning";
  return "danger";
}

type PatientData = {
  name: string;
  treatment_status: string | null;
  treatment_phase: string | null;
  treatment_day: number;
  treatment_total_days: number | null;
};

type AppointmentData = {
  date: string;
  time: string;
  doctor: string;
  modality: string;
};

type TreatmentSummary = {
  product: string;
  dose: string | null;
  frequency: string | null;
  cbd_mg: number | null;
  thc_mg: number | null;
};

type EvolutionMetric = {
  label: string;
  value: number;
  prev: number;
};

type EvolutionData = Record<string, EvolutionMetric>;

export default function PatientDashboardPage() {
  const { data: session } = useApiSession();
  const [selectedMood, setSelectedMood] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [patient, setPatient] = useState<PatientData | null>(null);
  const [appointment, setAppointment] = useState<AppointmentData | null>(null);
  const [treatment, setTreatment] = useState<TreatmentSummary | null>(null);
  const [evolution, setEvolution] = useState<EvolutionData | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const [profileRes, evolutionRes] = await Promise.all([
          getPatientProfile(),
          getPatientEvolution(),
        ]);
        if (cancelled) return;
        const profileData = profileRes.data as Record<string, unknown>;
        setPatient(profileData.patient as PatientData);
        setAppointment((profileData.appointment as AppointmentData) ?? null);
        setTreatment((profileData.treatment as TreatmentSummary) ?? null);
        const evoData = evolutionRes.data as Record<string, unknown>;
        setEvolution((evoData.evolution as EvolutionData) ?? null);
      } catch {
        if (!cancelled)
          setError("Nao foi possivel carregar seus dados. Tente novamente mais tarde.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchData();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
        <p className="text-on-surface-variant text-sm">{error}</p>
      </div>
    );
  }

  const patientName = session?.user?.username ?? patient?.name ?? "Paciente";
  const totalDays = patient?.treatment_total_days ?? 0;
  const progress =
    patient && totalDays > 0 ? Math.round((patient.treatment_day / totalDays) * 100) : 0;

  return (
    <div className="max-w-md mx-auto space-y-6">
      {/* ── Welcome Section ── */}
      <section>
        <h1 className="text-2xl font-headline font-extrabold tracking-tight text-on-surface">
          Ola, {patientName}
        </h1>
        <p className="text-on-surface-variant text-sm mt-1">
          Sua jornada de cuidado botanico continua hoje.
        </p>
      </section>

      {/* ── Highlight Card: Next Appointment + Treatment Status ── */}
      <Card variant="glass" padding="md" className="space-y-6">
        <div className="flex justify-between items-start">
          <div>
            <p className="text-[10px] uppercase tracking-widest font-bold text-primary/80 mb-1">
              Proximo Agendamento
            </p>
            <h3 className="text-lg font-headline font-bold">
              {appointment?.date ?? "Nenhum agendamento"}
            </h3>
            {appointment && (
              <p className="text-sm text-on-surface-variant">
                {appointment.time} &bull; {appointment.doctor} ({appointment.modality})
              </p>
            )}
          </div>
          <div className="bg-primary/20 p-2 rounded-full">
            <MaterialIcon icon="event" className="text-primary" />
          </div>
        </div>

        {patient && (patient.treatment_phase || totalDays > 0) && (
          <div className="pt-4 border-t border-white/5">
            <div className="flex justify-between items-center mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-on-surface">
                Status do Tratamento
              </span>
              {patient.treatment_phase && <Badge tone="primary">{patient.treatment_phase}</Badge>}
            </div>
            {totalDays > 0 && (
              <>
                <ProgressBar value={progress} variant="primary" size="md" glow />
                <div className="flex justify-between mt-2">
                  <span className="text-[10px] text-stone-500">
                    Dia {patient.treatment_day} de {totalDays}
                  </span>
                  <span className="text-[10px] text-stone-500">{progress}% concluido</span>
                </div>
              </>
            )}
          </div>
        )}
      </Card>

      {/* ── CTA: Talk to Doctor ── */}
      <Link
        href="/p/consultas"
        className="flex items-center justify-between bg-primary p-5 rounded-2xl active:scale-95 transition-transform duration-200"
      >
        <div className="flex items-center gap-4">
          <div className="bg-on-primary rounded-full p-2">
            <MaterialIcon icon="chat" className="text-primary text-2xl" />
          </div>
          <div>
            <h4 className="font-bold text-on-primary leading-none">Falar com Medico</h4>
            <p className="text-on-primary/70 text-xs mt-1">Suporte imediato via WhatsApp</p>
          </div>
        </div>
        <MaterialIcon icon="arrow_forward" className="text-on-primary" />
      </Link>

      {/* ── Quick Mood Check ── */}
      <section className="space-y-4">
        <div className="flex justify-between items-center">
          <h2 className="font-headline font-bold text-lg">Diario de Sintomas</h2>
          <Link
            href="/p/diario"
            className="text-primary text-xs font-bold uppercase tracking-wider"
          >
            Ver Historico
          </Link>
        </div>
        <Card variant="glass" padding="md">
          <p className="text-sm text-center mb-6 text-on-surface-variant">
            Como voce esta se sentindo agora?
          </p>
          <div className="flex justify-between items-center">
            {MOOD_OPTIONS.map((opt, idx) => (
              <button
                key={opt.label}
                onClick={() => setSelectedMood(idx)}
                className={cn(
                  "flex flex-col items-center gap-2 group transition-all",
                  selectedMood === idx ? "scale-110" : "grayscale hover:grayscale-0",
                )}
              >
                <span className="text-3xl">{opt.emoji}</span>
                <span className="text-[10px] font-bold text-stone-500 uppercase">{opt.label}</span>
              </button>
            ))}
          </div>
        </Card>
      </section>

      {/* ── Quick Access Bento Grid ── */}
      <section className="grid grid-cols-2 gap-4">
        {QUICK_ACTIONS.map((action) => (
          <Link key={action.href} href={action.href}>
            <Card
              variant="glass"
              padding="sm"
              className="flex flex-col justify-between h-32 hover:border-primary/30 transition-colors"
            >
              <MaterialIcon icon={action.icon} className={action.color} />
              <div>
                <p className="text-sm font-bold">{action.label}</p>
              </div>
            </Card>
          </Link>
        ))}
      </section>

      {/* ── Treatment Summary ── */}
      {treatment && (
        <section className="space-y-4">
          <h2 className="font-headline font-bold text-lg">Resumo do Tratamento</h2>
          <Card variant="glass" padding="md">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
                <div className="flex items-center gap-2 mb-2">
                  <MaterialIcon icon="medication" size="sm" className="text-secondary" />
                  <span className="text-xs font-medium text-on-surface-variant">Produto</span>
                </div>
                <p className="text-sm font-bold">{treatment.product}</p>
              </div>
              <div className="bg-surface-container/40 p-4 rounded-lg border border-outline-variant/20">
                <div className="flex items-center gap-2 mb-2">
                  <MaterialIcon icon="water_drop" size="sm" className="text-primary" />
                  <span className="text-xs font-medium text-on-surface-variant">Posologia</span>
                </div>
                <p className="text-sm font-bold">
                  {[treatment.dose, treatment.frequency].filter(Boolean).join(" • ") || "A definir"}
                </p>
              </div>
            </div>
          </Card>
        </section>
      )}

      {/* ── Recent Evolution ── */}
      {evolution && Object.keys(evolution).length > 0 && (
        <section className="space-y-4 pb-4">
          <h2 className="font-headline font-bold text-lg">Evolucao Recente</h2>
          <Card variant="glass" padding="md" className="space-y-4">
            {Object.values(evolution).map((metric) => (
              <div key={metric.label}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-semibold text-on-surface">{metric.label}</span>
                  <span className="text-xs text-on-surface-variant">
                    {metric.value}%{" "}
                    <span
                      className={cn(
                        "text-[10px]",
                        metric.value > metric.prev ? "text-emerald-400" : "text-error",
                      )}
                    >
                      ({metric.value > metric.prev ? "+" : ""}
                      {metric.value - metric.prev}%)
                    </span>
                  </span>
                </div>
                <ProgressBar
                  value={metric.value}
                  variant={getEvolutionVariant(metric.value)}
                  size="sm"
                />
              </div>
            ))}
          </Card>
        </section>
      )}
    </div>
  );
}
