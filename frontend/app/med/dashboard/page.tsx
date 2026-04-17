"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";
import { getDashboard } from "@/lib/api";
import type { DashboardData } from "@/lib/types";
import {
  StatCard,
  Card,
  Badge,
  ProgressBar,
  MaterialIcon,
  Button,
} from "@/components/ui-tw";

/* ── Types for API response data ── */

type PatientInfo = {
  name: string;
  id: string;
  unit: string;
  condition: string;
};

type AiAnalysis = {
  date: string;
  terpene: string;
  text_paragraph_1: string;
  text_paragraph_2: string;
  recommendation: string;
  stats: { value: string; label: string }[];
};

type Prescription = {
  id: number;
  name: string;
  type: string;
  dosage: string;
  remaining: string;
  status: "ATIVO" | "VENCIDO";
  icon: string;
};

type PhysicalStatus = {
  score: number;
  description: string;
};

type EmotionalStatus = {
  label: string;
  level: string;
  value: number;
  variant: "success" | "warning" | "primary";
};

type AppointmentInfo = {
  id: number;
  patient: string;
  date: string;
  time: string;
  type: string;
};

type ClinicalData = {
  patient: PatientInfo;
  ai_analysis: AiAnalysis;
  prescriptions: Prescription[];
  physical: PhysicalStatus;
  emotional: EmotionalStatus[];
  appointments: AppointmentInfo[];
};

export default function DashboardPage() {
  const [dashData, setDashData] = useState<DashboardData | null>(null);
  const [clinical, setClinical] = useState<ClinicalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDashboard()
      .then((data) => {
        if (cancelled) return;
        setDashData(data);
        // The API may include clinical data alongside metrics
        const d = data as unknown as Record<string, unknown>;
        if (d.clinical) {
          setClinical(d.clinical as ClinicalData);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Nao foi possivel carregar o painel. Tente novamente mais tarde.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const metrics = dashData?.metrics;
  const patient = clinical?.patient ?? { name: "", id: "", unit: "", condition: "" };
  const aiAnalysis = clinical?.ai_analysis;
  const prescriptions = clinical?.prescriptions ?? [];
  const physical = clinical?.physical ?? { score: 0, description: "Aguardando dados..." };
  const emotional = clinical?.emotional ?? [];
  const appointments = clinical?.appointments ?? [];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando painel...</p>
        </div>
      </div>
    );
  }

  if (error && !dashData) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
          <p className="text-on-surface-variant text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Painel de Controle
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            {patient.id ? `Monitorando Paciente ${patient.id} - Analise em tempo real` : "Monitoramento clinico em tempo real"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
          >
            <MaterialIcon icon="file_download" size="sm" />
            <span className="hidden sm:inline ml-1">Exportar Relatorio</span>
          </Button>
          <Button size="sm">
            <MaterialIcon icon="add" size="sm" />
            <span className="ml-1">Nova Prescricao</span>
          </Button>
        </div>
      </div>

      {/* ── KPI Cards — dados reais da API ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <StatCard
          icon="group"
          label="Pacientes"
          value={metrics?.total_patients ?? 0}
        />
        <StatCard
          icon="event"
          label="Agendamentos"
          value={metrics?.total_appointments ?? 0}
        />
        <StatCard
          icon="psychology"
          label="Analises IA"
          value={metrics?.total_ai ?? 0}
        />
        <StatCard
          icon="chat"
          label="Mensagens"
          value={metrics?.total_messages ?? 0}
        />
      </div>

      {/* ── Main Grid: 2 columns desktop, 1 mobile ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* LEFT COLUMN (2/3 width) */}
        <div className="lg:col-span-2 space-y-6">
          {/* Inteligencia Botanica Card */}
          {aiAnalysis && (
            <div className="glass-panel rounded-3xl p-6 md:p-8 relative overflow-hidden border-primary/5">
              <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-[80px] -mr-32 -mt-32 pointer-events-none" />
              <div className="relative z-10 space-y-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center shadow-lg shadow-primary/20">
                    <MaterialIcon icon="psychology" className="text-on-primary font-bold" size="lg" />
                  </div>
                  <div>
                    <h3 className="text-lg md:text-xl font-black text-on-surface">
                      Analise de Inteligencia Botanica
                    </h3>
                    <p className="text-stone-500 text-sm">Protocolo Clinico IA v4.2</p>
                  </div>
                </div>
                <div className="bg-surface-container/50 p-4 md:p-6 rounded-2xl border border-white/5 leading-relaxed text-stone-300 text-sm md:text-base">
                  <p className="mb-4">{aiAnalysis.text_paragraph_1}</p>
                  <p className="mb-4">{aiAnalysis.text_paragraph_2}</p>
                  <div className="flex items-center gap-3 p-3 bg-primary/5 border-l-4 border-primary rounded-r-lg">
                    <MaterialIcon icon="lightbulb" className="text-primary" />
                    <p className="text-sm font-medium">{aiAnalysis.recommendation}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4">
                  {aiAnalysis.stats.map((stat) => (
                    <div key={stat.label} className="text-center">
                      <div className="text-xl md:text-2xl font-black text-primary">{stat.value}</div>
                      <div className="text-[10px] font-bold text-stone-500 uppercase tracking-tighter">
                        {stat.label}
                      </div>
                    </div>
                  ))}
                </div>
                <Button className="w-full sm:w-auto">
                  Ver Analise Completa
                  <MaterialIcon icon="arrow_forward" size="sm" className="ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* ── Prescriptions Section ── */}
          {prescriptions.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-black text-on-surface font-headline">
                  Prescricoes Ativas
                </h3>
                <a
                  className="text-sm font-bold text-primary flex items-center gap-1 hover:underline cursor-pointer"
                  href="/med/prescricao"
                >
                  Historico Completo
                  <MaterialIcon icon="arrow_forward" size="sm" />
                </a>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {prescriptions.map((rx) => {
                  const isExpired = rx.status === "VENCIDO";
                  return (
                    <div
                      key={rx.id}
                      className={cn(
                        "glass-panel p-4 rounded-2xl flex gap-4 hover:border-primary/20 transition-all cursor-pointer",
                        isExpired && "border-error/10 hover:border-error/30",
                      )}
                    >
                      <div
                        className={cn(
                          "w-14 h-14 md:w-16 md:h-16 bg-surface-container rounded-xl flex items-center justify-center flex-shrink-0 border",
                          isExpired ? "border-error/5" : "border-white/5",
                        )}
                      >
                        <MaterialIcon
                          icon={rx.icon}
                          size="lg"
                          className={isExpired ? "text-error" : "text-primary"}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start gap-2">
                          <h5 className="font-bold text-on-surface truncate text-sm">{rx.name}</h5>
                          <Badge tone={isExpired ? "danger" : "primary"}>{rx.status}</Badge>
                        </div>
                        <p className="text-xs text-stone-500 mb-2">{rx.type}</p>
                        <div className="flex items-center gap-3 flex-wrap">
                          {rx.dosage && (
                            <div className="flex items-center gap-1 text-[10px] font-bold text-stone-400">
                              <MaterialIcon icon="medication" size="sm" />
                              {rx.dosage}
                            </div>
                          )}
                          <div
                            className={cn(
                              "flex items-center gap-1 text-[10px] font-bold",
                              isExpired ? "text-error" : "text-stone-400",
                            )}
                          >
                            {!isExpired && <MaterialIcon icon="calendar_today" size="sm" />}
                            {rx.remaining}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN (1/3 width) */}
        <div className="space-y-6">
          {/* Physical Status */}
          <Card variant="glass" padding="md" className="rounded-3xl border-primary/5">
            <div className="flex justify-between items-center mb-6">
              <h4 className="font-bold text-on-surface">Status Fisico</h4>
              <MaterialIcon icon="monitoring" className="text-stone-500" />
            </div>
            <div className="flex flex-col items-center justify-center space-y-4">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 128 128">
                  <circle
                    className="text-surface-container-highest"
                    cx="64"
                    cy="64"
                    r="58"
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth="8"
                  />
                  <circle
                    className="text-primary"
                    cx="64"
                    cy="64"
                    r="58"
                    fill="transparent"
                    stroke="currentColor"
                    strokeWidth="8"
                    strokeDasharray={2 * Math.PI * 58}
                    strokeDashoffset={2 * Math.PI * 58 * (1 - physical.score / 100)}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute flex flex-col items-center">
                  <span className="text-2xl font-black">{physical.score}%</span>
                  <span className="text-[10px] font-bold text-stone-500">
                    {physical.score >= 70 ? "OTIMO" : physical.score >= 40 ? "BOM" : "ATENCAO"}
                  </span>
                </div>
              </div>
              <p className="text-sm font-medium text-stone-400 text-center">
                {physical.description}
              </p>
            </div>
          </Card>

          {/* Emotional Status */}
          {emotional.length > 0 && (
            <Card variant="glass" padding="md" className="rounded-3xl border-primary/5">
              <div className="flex justify-between items-center mb-6">
                <h4 className="font-bold text-on-surface">Status Emocional</h4>
                <MaterialIcon icon="psychology_alt" className="text-stone-500" />
              </div>
              <div className="space-y-4">
                {emotional.map((item) => (
                  <div key={item.label} className="space-y-1">
                    <div className="flex justify-between text-xs font-bold uppercase text-stone-500">
                      <span>{item.label}</span>
                      <span className="text-on-surface">{item.level}</span>
                    </div>
                    <ProgressBar
                      value={item.value}
                      variant={item.variant}
                      size="sm"
                    />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Upcoming Appointments */}
          {appointments.length > 0 && (
            <Card variant="glass" padding="md" className="rounded-3xl border-primary/5">
              <div className="flex justify-between items-center mb-4">
                <h4 className="font-bold text-on-surface">Proximas Consultas</h4>
                <MaterialIcon icon="calendar_month" className="text-stone-500" />
              </div>
              <div className="space-y-3">
                {appointments.map((appt) => (
                  <div
                    key={appt.id}
                    className="flex items-center gap-3 p-3 rounded-xl bg-surface-container/50 border border-white/5 hover:border-primary/20 transition-all cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <MaterialIcon icon="event" size="sm" className="text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-bold text-on-surface truncate">{appt.patient}</p>
                      <p className="text-[10px] text-stone-500">
                        {appt.date} as {appt.time} - {appt.type}
                      </p>
                    </div>
                    <MaterialIcon icon="chevron_right" size="sm" className="text-stone-500" />
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </section>
  );
}
