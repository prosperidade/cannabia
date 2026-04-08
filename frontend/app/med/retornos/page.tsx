"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { listReturns } from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  StatCard,
  SearchBar,
  MaterialIcon,
  Avatar,
  ProgressBar,
} from "@/components/ui-tw";

type ReturnReason =
  | "ajuste_de_dose"
  | "retorno_agendado"
  | "alerta_ia"
  | "acompanhamento";

type SymptomTrend = "melhorando" | "estavel" | "piorando";

type PatientReturn = {
  id: number;
  name: string;
  avatarUrl?: string;
  treatment: {
    ratio: string;
    dosage: string;
  };
  lastConsultation: string;
  returnReason: ReturnReason;
  symptomTrend: SymptomTrend;
  aiRecommendation: string;
  status: "pendente" | "agendado" | "concluido";
};

type ReturnsStats = {
  patientsInReturn: number;
  pendingAdjustments: number;
  scheduledReturns: number;
  adherenceRate: number;
};

/* ──────────────── Helpers ──────────────── */

const REASON_CONFIG: Record<ReturnReason, { label: string; tone: "warning" | "info" | "danger" | "primary" }> = {
  ajuste_de_dose: { label: "Ajuste de Dose", tone: "warning" },
  retorno_agendado: { label: "Retorno Agendado", tone: "info" },
  alerta_ia: { label: "Alerta IA", tone: "danger" },
  acompanhamento: { label: "Acompanhamento", tone: "primary" },
};

const TREND_CONFIG: Record<SymptomTrend, { label: string; icon: string; color: string }> = {
  melhorando: { label: "Melhorando", icon: "trending_up", color: "text-emerald-400" },
  estavel: { label: "Estavel", icon: "trending_flat", color: "text-amber-400" },
  piorando: { label: "Piorando", icon: "trending_down", color: "text-error" },
};

const STATUS_CONFIG: Record<string, { label: string; tone: "success" | "warning" | "info" | "neutral" }> = {
  pendente: { label: "Aguardando revisao", tone: "warning" },
  agendado: { label: "Agendado", tone: "info" },
  concluido: { label: "Concluido", tone: "success" },
};

type PeriodFilter = "7d" | "30d" | "90d";
type StatusFilter = "todos" | "pendente" | "agendado" | "concluido";

/* ──────────────── Component ──────────────── */

export default function RetornosPage() {
  const router = useRouter();
  const { loading, data: session } = useApiSession();

  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState<PeriodFilter>("30d");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("todos");
  const [patients, setPatients] = useState<PatientReturn[]>([]);
  const [stats, setStats] = useState<ReturnsStats>({ patientsInReturn: 0, pendingAdjustments: 0, scheduledReturns: 0, adherenceRate: 0 });
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!loading && (!session?.authenticated || !session.user)) {
      router.replace("/login");
    }
  }, [loading, session, router]);

  // Fetch returns data from API
  useEffect(() => {
    let cancelled = false;
    async function fetchReturns() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await listReturns();
        if (cancelled) return;

        // API returns { data: [...items], meta: { total_returns, pending, scheduled, ... } }
        const rawItems = (Array.isArray(res.data) ? res.data : []) as Record<string, unknown>[];
        const meta = (res as Record<string, unknown>).meta as Record<string, number> | undefined;

        // Map backend shape to PatientReturn
        const mapped: PatientReturn[] = rawItems.map((item) => {
          const treatmentStatus = (item.treatment_status as string) || "pendente";
          let status: PatientReturn["status"] = "pendente";
          if (treatmentStatus === "ativo" || treatmentStatus === "pendente") status = "pendente";
          else if (treatmentStatus === "agendado") status = "agendado";
          else if (treatmentStatus === "concluido") status = "concluido";

          // Determine return reason based on available data
          let returnReason: ReturnReason = "acompanhamento";
          const nextReturn = item.next_return_date ? new Date(item.next_return_date as string) : null;
          const now = new Date();
          if (nextReturn && nextReturn < now) returnReason = "alerta_ia";
          else if (nextReturn && nextReturn.getTime() - now.getTime() < 3 * 86400000) returnReason = "ajuste_de_dose";
          else if (nextReturn) returnReason = "retorno_agendado";

          // Determine symptom trend from ai_recommendation text
          const aiRec = (item.ai_recommendation as string) || "";
          let symptomTrend: SymptomTrend = "estavel";
          if (/melhora|reduc|reduzi/i.test(aiRec)) symptomTrend = "melhorando";
          else if (/piora|efeitos colaterais|atrasado/i.test(aiRec)) symptomTrend = "piorando";

          const lastUpdate = item.last_update as string | undefined;

          return {
            id: (item.treatment_plan_id as number) || (item.patient_id as number) || 0,
            name: (item.patient_name as string) || "Sem nome",
            treatment: {
              ratio: (item.cbd_thc_ratio as string) || "N/A",
              dosage: (item.dosage as string) || "N/A",
            },
            lastConsultation: lastUpdate
              ? new Date(lastUpdate).toLocaleDateString("pt-BR")
              : "N/A",
            returnReason,
            symptomTrend,
            aiRecommendation: aiRec || "Sem recomendacao disponivel.",
            status,
          };
        });

        setPatients(mapped);

        if (meta) {
          setStats({
            patientsInReturn: meta.total_returns ?? mapped.length,
            pendingAdjustments: meta.pending ?? 0,
            scheduledReturns: meta.scheduled ?? 0,
            adherenceRate: meta.total_returns ? Math.round(((meta.total_returns - (meta.pending ?? 0)) / meta.total_returns) * 100) : 0,
          });
        }
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar os retornos.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    if (session?.authenticated) fetchReturns();
    return () => { cancelled = true; };
  }, [session?.authenticated]);

  const filteredPatients = useMemo(() => {
    return patients.filter((p) => {
      const matchesSearch =
        !search || p.name.toLowerCase().includes(search.toLowerCase());
      const matchesStatus =
        statusFilter === "todos" || p.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [patients, search, statusFilter]);

  if (loading || apiLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando...</p>
        </div>
      </div>
    );
  }

  if (apiError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
          <p className="text-on-surface-variant text-sm">{apiError}</p>
        </div>
      </div>
    );
  }

  if (!session?.authenticated || !session.user) {
    return null;
  }

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="space-y-2">
        <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
          Retornos e Ajustes
        </h2>
        <p className="text-stone-500 font-medium text-sm flex items-center gap-2">
          <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
          Painel de Acompanhamento - Monitoramento clinico assistido por IA
        </p>
      </div>

      {/* ── Stats Row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {/* TODO: Replace static values with API data */}
        <StatCard
          icon="diversity_3"
          label="Pacientes em Retorno"
          value={stats.patientsInReturn}
          delta="+3 esta semana"
          deltaType="up"
        />
        <StatCard
          icon="pending_actions"
          label="Ajustes Pendentes"
          value={stats.pendingAdjustments}
          delta="Revisao em 24h"
          deltaType="down"
          className="border-l-2 border-l-amber-500/50"
        />
        <StatCard
          icon="event"
          label="Retornos Agendados"
          value={stats.scheduledReturns}
          delta="Proximos 30 dias"
          deltaType="neutral"
        />
        <div className="glass-panel rounded-2xl p-5 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary/10">
              <MaterialIcon icon="query_stats" size="lg" className="text-primary" />
            </div>
            <span className="text-xs font-bold text-emerald-400">+2.1%</span>
          </div>
          <div>
            <p className="text-2xl font-black text-primary font-headline">
              {stats.adherenceRate}%
            </p>
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
              Taxa de Adesao
            </p>
            <ProgressBar
              value={stats.adherenceRate}
              variant="primary"
              size="sm"
              glow
              className="mt-2"
            />
          </div>
        </div>
      </div>

      {/* ── Filter Bar ── */}
      <div className="flex flex-col md:flex-row gap-3 md:items-center">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar paciente..."
          className="flex-1 md:max-w-sm sticky top-0 z-10 md:static"
        />

        {/* Period filter */}
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
          {(["7d", "30d", "90d"] as PeriodFilter[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-all whitespace-nowrap",
                period === p
                  ? "bg-primary text-on-primary-container"
                  : "glass-panel text-stone-400 hover:text-on-surface hover:bg-white/5",
              )}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Status filter */}
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar">
          {(["todos", "pendente", "agendado", "concluido"] as StatusFilter[]).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                "px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-widest transition-all whitespace-nowrap",
                statusFilter === s
                  ? "bg-primary/15 text-primary border border-primary/30"
                  : "glass-panel text-stone-400 hover:text-on-surface hover:bg-white/5",
              )}
            >
              {s === "todos" ? "Todos" : STATUS_CONFIG[s].label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Patient Return Cards ── */}
      {filteredPatients.length === 0 ? (
        /* Empty State */
        <Card variant="glass" padding="lg" className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center mb-6">
            <MaterialIcon icon="event_available" size="lg" className="text-primary/50" />
          </div>
          <h3 className="text-lg font-bold text-on-surface font-headline mb-2">
            Nenhum retorno pendente
          </h3>
          <p className="text-stone-500 text-sm max-w-md">
            Todos os pacientes estao em dia com seus protocolos. Novos alertas
            aparecerão aqui quando a IA identificar necessidade de ajuste.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredPatients.map((patient) => {
            const reason = REASON_CONFIG[patient.returnReason];
            const trend = TREND_CONFIG[patient.symptomTrend];
            const status = STATUS_CONFIG[patient.status];

            return (
              <Card
                key={patient.id}
                variant="glass"
                padding="md"
                className={cn(
                  "hover:border-primary/20 transition-all",
                  patient.returnReason === "alerta_ia" && "border-l-4 border-l-error/50",
                  patient.returnReason === "ajuste_de_dose" && "border-l-4 border-l-amber-500/50",
                )}
              >
                {/* ── Card Top: Avatar + Info + Badges ── */}
                <div className="flex flex-col md:flex-row md:items-start gap-4">
                  {/* Left: Avatar + Patient info */}
                  <div className="flex items-start gap-4 flex-1 min-w-0">
                    <Avatar name={patient.name} src={patient.avatarUrl} size="lg" />
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h4 className="text-base font-bold text-on-surface truncate">
                          {patient.name}
                        </h4>
                        <Badge tone={reason.tone}>{reason.label}</Badge>
                        <Badge tone={status.tone}>{status.label}</Badge>
                      </div>

                      {/* Treatment info */}
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone-400 mb-2">
                        <span className="flex items-center gap-1">
                          <MaterialIcon icon="medication" size="sm" className="text-primary/70" />
                          {patient.treatment.ratio}
                        </span>
                        <span className="flex items-center gap-1">
                          <MaterialIcon icon="schedule" size="sm" className="text-stone-500" />
                          {patient.treatment.dosage}
                        </span>
                        <span className="flex items-center gap-1">
                          <MaterialIcon icon="calendar_today" size="sm" className="text-stone-500" />
                          Ultima: {patient.lastConsultation}
                        </span>
                      </div>

                      {/* Symptom Trend */}
                      <div className="flex items-center gap-2 mb-3">
                        <span className={cn("flex items-center gap-1 text-xs font-bold", trend.color)}>
                          <MaterialIcon icon={trend.icon} size="sm" />
                          {trend.label}
                        </span>
                      </div>

                      {/* AI Recommendation */}
                      <div className="flex items-start gap-2 p-3 bg-surface-container/50 border border-white/5 rounded-xl">
                        <MaterialIcon
                          icon="auto_awesome"
                          size="sm"
                          className="text-primary mt-0.5 flex-shrink-0"
                        />
                        <p className="text-xs text-stone-300 leading-relaxed">
                          {patient.aiRecommendation}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex flex-row md:flex-col gap-2 md:items-end flex-shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-white/5">
                    <Button
                      size="sm"
                      icon="event"
                      className="flex-1 md:flex-none"
                    >
                      Agendar Retorno
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="tune"
                      className="flex-1 md:flex-none"
                    >
                      Ajustar Dose
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="description"
                      className="flex-1 md:flex-none"
                      onClick={() => {
                        // TODO: Navigate to patient medical record
                        // router.push(`/med/atendimentos/${patient.id}`);
                      }}
                    >
                      <span className="hidden sm:inline">Ver Prontuario</span>
                      <span className="sm:hidden">Prontuario</span>
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}
