"use client";

import { useEffect, useState } from "react";

import { Card, MaterialIcon, Badge, Avatar } from "@/components/ui-tw";
import {
  getAcompanhamentoOverview,
  getAcompanhamentoActivePatients,
  listAppointments,
  type AcompanhamentoOverview,
  type ActivePatient,
} from "@/lib/api";
import type { AppointmentItem } from "@/lib/types";
import { useApiSession } from "@/lib/use-api-session";

/**
 * Pagina de Acompanhamento — cuidado continuo dos pacientes entre
 * consultas, alimentado pelos agentes IA (Triagem, Anamnese, FollowUp,
 * Regulatorio).
 *
 * Visivel para: Medico, Recepcao, AdminClinica, Admin global.
 */
export default function AcompanhamentoPage() {
  const { data: session } = useApiSession();
  const userName = session?.user?.username ?? "";

  const [overview, setOverview] = useState<AcompanhamentoOverview | null>(null);
  const [todayAgenda, setTodayAgenda] = useState<AppointmentItem[]>([]);
  const [activePatients, setActivePatients] = useState<ActivePatient[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErrorMsg(null);

    Promise.all([
      getAcompanhamentoOverview(),
      // Agenda do dia — falha aqui nao bloqueia os KPIs
      // Sprint 3 Page-Migration: envelope `Paginated<AppointmentItem>`.
      listAppointments({ limit: 200 })
        .then((env) => env.items)
        .catch(() => [] as AppointmentItem[]),
      // Lista de pacientes em acompanhamento — falha nao bloqueia o resto
      getAcompanhamentoActivePatients(20).catch(() => ({ items: [], count: 0 })),
    ])
      .then(([ov, appts, active]) => {
        if (!alive) return;
        setOverview(ov);
        const today = new Date().toISOString().slice(0, 10);
        const filtered = (Array.isArray(appts) ? appts : [])
          .filter(
            (a) =>
              typeof a.appointment_date === "string" &&
              a.appointment_date.startsWith(today),
          )
          .sort((a, b) => a.appointment_date.localeCompare(b.appointment_date));
        setTodayAgenda(filtered);
        setActivePatients(active.items ?? []);
      })
      .catch((err) => {
        if (!alive) return;
        const msg =
          err instanceof Error ? err.message : "Falha ao carregar dados.";
        setErrorMsg(msg);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const kpis = overview?.kpis;
  const agents = overview?.agents_activity_24h ?? [];
  const totalActions = agents.reduce((sum, a) => sum + a.actions, 0);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl md:text-3xl font-headline font-extrabold tracking-tight text-on-surface">
          Acompanhamento
        </h1>
        <p className="text-sm text-stone-500 mt-1">
          Cuidado continuo dos pacientes entre consultas. Os agentes IA
          monitoram e sinalizam o que precisa de atencao humana.
        </p>
      </header>

      {errorMsg && (
        <Card padding="md" className="border-error/40 bg-error/5">
          <div className="flex items-center gap-3 text-error">
            <MaterialIcon icon="error" />
            <p className="text-sm">Nao foi possivel carregar: {errorMsg}</p>
          </div>
        </Card>
      )}

      {/* KPIs do dia */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          icon="warning"
          tone="danger"
          label="Pacientes em risco"
          value={renderKpi(loading, kpis?.patients_at_risk)}
          hint="eventos graves sem parecer clinico ainda"
        />
        <KpiCard
          icon="schedule"
          tone="warning"
          label="Follow-ups pendentes"
          value={renderKpi(loading, kpis?.followups_pending)}
          hint="aguardando resposta do paciente (D+3 / D+7 / D+15)"
        />
        <KpiCard
          icon="medical_services"
          tone="info"
          label="Triagens em andamento"
          value={renderKpi(loading, kpis?.triages_in_progress)}
          hint="links de triagem ativos ainda nao usados"
        />
        <KpiCard
          icon="report"
          tone="danger"
          label="Eventos adversos abertos"
          value={renderKpi(loading, kpis?.adverse_events_open)}
          hint="sem outcome registrado ainda"
        />
      </section>

      {/* Agenda de hoje (uso primario: Recepcao) */}
      <Card padding="lg">
        <div className="flex items-start justify-between mb-5 gap-3">
          <SectionHeader
            icon="calendar_today"
            title="Agenda de hoje"
            desc={
              loading
                ? "Carregando..."
                : `${todayAgenda.length} agendamento${
                    todayAgenda.length === 1 ? "" : "s"
                  } para hoje`
            }
          />
          <a href="/org/agendamentos" className="text-primary text-xs font-bold hover:underline">
            Abrir agenda
          </a>
        </div>
        {loading ? (
          <ul className="space-y-2">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-14 rounded-xl bg-surface-container-low/60 animate-pulse"
              />
            ))}
          </ul>
        ) : todayAgenda.length === 0 ? (
          <EmptyState
            icon="event_busy"
            title="Sem agendamentos para hoje"
            subtitle="Aproveite para retomar follow-ups e revisar pacientes em risco."
          />
        ) : (
          <ul className="space-y-2">
            {todayAgenda.slice(0, 8).map((a) => (
              <AgendaRow key={a.id} appt={a} />
            ))}
            {todayAgenda.length > 8 && (
              <li className="pt-2 text-center text-xs text-stone-500">
                + {todayAgenda.length - 8} agendamento
                {todayAgenda.length - 8 === 1 ? "" : "s"} —{" "}
                <a
                  href="/org/agendamentos"
                  className="text-primary font-bold hover:underline"
                >
                  ver tudo
                </a>
              </li>
            )}
          </ul>
        )}
      </Card>

      {/* Alertas — placeholder ate definir motor de alertas */}
      <Card padding="lg">
        <SectionHeader
          icon="notifications_active"
          title="Alertas para a equipe"
          desc="Escalacoes que precisam de acao humana hoje."
        />
        <EmptyState
          icon="check_circle"
          title="Nenhum alerta no momento"
          subtitle="Os agentes nao detectaram nada que precise de intervencao agora."
        />
      </Card>

      {/* Atividade dos agentes */}
      <Card padding="lg">
        <div className="flex items-start justify-between mb-5 gap-3">
          <SectionHeader
            icon="auto_awesome"
            title="Atividade dos agentes hoje"
            desc="Transparencia: o que os agentes IA fizeram autonomamente."
          />
          <Badge tone={totalActions > 0 ? "info" : "neutral"}>
            {loading ? "Carregando..." : `${totalActions} acoes / 24h`}
          </Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(agents.length > 0
            ? agents
            : ([
                { agent: "Triagem", actions: 0, last_action_at: null },
                { agent: "Anamnese", actions: 0, last_action_at: null },
                { agent: "FollowUp", actions: 0, last_action_at: null },
                { agent: "Regulatorio", actions: 0, last_action_at: null },
              ] as AcompanhamentoOverview["agents_activity_24h"])
          ).map((a) => (
            <AgentActivityRow
              key={a.agent}
              agent={a.agent}
              summary={renderAgentSummary(loading, a.actions, a.last_action_at)}
            />
          ))}
        </div>
      </Card>

      {/* Lista de pacientes em acompanhamento ativo */}
      <Card padding="lg">
        <SectionHeader
          icon="favorite"
          title="Pacientes em acompanhamento ativo"
          desc={`${activePatients.length} pacientes com plano terapeutico vigente.`}
        />
        {loading ? (
          <p className="text-sm text-stone-500 py-4">Carregando lista...</p>
        ) : activePatients.length === 0 ? (
          <EmptyState
            icon="hourglass_empty"
            title="Sem pacientes ativos"
            subtitle="Pacientes com plano terapeutico ativo aparecem aqui assim que forem cadastrados."
          />
        ) : (
          <ul className="divide-y divide-white/5">
            {activePatients.map((p) => (
              <ActivePatientRow key={p.patient_id} patient={p} />
            ))}
          </ul>
        )}
      </Card>

      {userName && (
        <p className="text-[11px] text-stone-500 text-center pt-4">
          Logado como <span className="text-on-surface">{userName}</span>
          {overview && (
            <>
              {" "}— atualizado{" "}
              <span className="text-on-surface">
                {formatTimestamp(overview.generated_at)}
              </span>
            </>
          )}
        </p>
      )}
    </div>
  );
}

/* ── Helpers de renderizacao ──────────────────────────────────── */

function renderKpi(loading: boolean, value: number | undefined): string {
  if (loading) return "...";
  if (value === undefined) return "—";
  return String(value);
}

function renderAgentSummary(
  loading: boolean,
  actions: number,
  lastAt: string | null,
): string {
  if (loading) return "Carregando atividade...";
  if (actions === 0) return "Sem atividade nas ultimas 24h.";
  const when = lastAt ? formatTimestamp(lastAt) : "ha pouco";
  return `${actions} acao${actions === 1 ? "" : "es"} — ultima ${when}`;
}

function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/* ── Componentes internos ─────────────────────────────────────── */

function KpiCard({
  icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: string;
  label: string;
  value: string;
  hint: string;
  tone: "info" | "warning" | "danger" | "success";
}) {
  const toneStyles = {
    info: "bg-primary/10 text-primary",
    warning: "bg-amber-500/10 text-amber-300",
    danger: "bg-error/10 text-error",
    success: "bg-emerald-500/10 text-emerald-300",
  } as const;
  return (
    <Card variant="glass" padding="md" className="space-y-3">
      <div
        className={`w-10 h-10 rounded-xl flex items-center justify-center ${toneStyles[tone]}`}
      >
        <MaterialIcon icon={icon} />
      </div>
      <div>
        <p className="text-2xl font-headline font-extrabold text-on-surface leading-none">
          {value}
        </p>
        <p className="text-xs font-bold text-on-surface mt-1">{label}</p>
        <p className="text-[11px] text-stone-500 mt-1">{hint}</p>
      </div>
    </Card>
  );
}

function SectionHeader({
  icon,
  title,
  desc,
}: {
  icon: string;
  title: string;
  desc?: string;
}) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
        <MaterialIcon icon={icon} className="text-primary" />
      </div>
      <div>
        <h3 className="text-lg font-headline font-bold text-on-surface leading-tight">
          {title}
        </h3>
        {desc && <p className="text-xs text-stone-500 mt-0.5">{desc}</p>}
      </div>
    </div>
  );
}

function EmptyState({
  icon,
  title,
  subtitle,
}: {
  icon: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="py-10 flex flex-col items-center justify-center text-center gap-2">
      <MaterialIcon icon={icon} size="xl" className="text-stone-600" />
      <p className="text-sm font-bold text-on-surface">{title}</p>
      <p className="text-xs text-stone-500 max-w-md">{subtitle}</p>
    </div>
  );
}

function ActivePatientRow({ patient }: { patient: ActivePatient }) {
  const followup = mapFollowupStatus(patient.followup_status);
  const returnLabel = renderReturnLabel(patient.next_return_in_days);
  const returnTone = returnToneFor(patient.next_return_in_days);
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <Avatar name={patient.patient_name || "Paciente"} size="sm" />
      <div className="flex-1 min-w-[160px]">
        <p className="text-sm font-bold text-on-surface truncate">
          {patient.patient_name}
        </p>
        <p className="text-[11px] text-stone-500 truncate">
          {patient.plan_name ?? "Plano sem nome"}
          {patient.dosage ? ` · ${patient.dosage}` : ""}
          {patient.frequency ? ` · ${patient.frequency}` : ""}
        </p>
      </div>
      <div className="text-right text-[11px] text-stone-500">
        <p className="text-on-surface font-bold">Dia {patient.days_in_treatment}</p>
        <p>de tratamento</p>
      </div>
      {returnLabel && (
        <Badge tone={returnTone}>{returnLabel}</Badge>
      )}
      {followup && <Badge tone={followup.tone}>{followup.label}</Badge>}
    </li>
  );
}

function renderReturnLabel(days: number | null): string | null {
  if (days === null || days === undefined) return null;
  if (days < 0) return `Retorno atrasado ${Math.abs(days)}d`;
  if (days === 0) return "Retorno hoje";
  if (days === 1) return "Retorno amanha";
  if (days <= 7) return `Retorno em ${days}d`;
  return `Retorno em ${days}d`;
}

function returnToneFor(
  days: number | null,
): "primary" | "success" | "warning" | "danger" | "neutral" {
  if (days === null || days === undefined) return "neutral";
  if (days < 0) return "danger";
  if (days <= 1) return "warning";
  if (days <= 7) return "primary";
  return "neutral";
}

function mapFollowupStatus(
  s: string | null,
): { label: string; tone: "primary" | "success" | "warning" | "danger" | "neutral" } | null {
  if (!s) return null;
  switch (s) {
    case "responded":
      return { label: "Respondeu", tone: "success" };
    case "sent":
      return { label: "Aguardando resposta", tone: "warning" };
    case "pending":
      return { label: "Follow-up agendado", tone: "primary" };
    case "failed":
      return { label: "Falha follow-up", tone: "danger" };
    case "cancelled":
      return { label: "Cancelado", tone: "neutral" };
    default:
      return null;
  }
}

function AgendaRow({ appt }: { appt: AppointmentItem }) {
  const time = formatTimeShort(appt.appointment_date);
  const status = (appt.status ?? "").toLowerCase();
  const statusLabel = mapAgendaStatus(status);
  return (
    <li className="flex items-center gap-3 p-3 rounded-xl bg-surface-container-low border border-outline-variant/20 hover:border-primary/30 transition-colors">
      <div className="w-12 text-center flex-shrink-0">
        <p className="text-xs font-bold text-on-surface">{time}</p>
      </div>
      <Avatar name={appt.patient_name || "Paciente"} size="sm" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-on-surface truncate">
          {appt.patient_name || "Paciente"}
        </p>
        <p className="text-[11px] text-stone-500">Consulta clinica</p>
      </div>
      {statusLabel && <Badge tone={statusLabel.tone}>{statusLabel.label}</Badge>}
    </li>
  );
}

function formatTimeShort(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "--:--";
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--:--";
  }
}

function mapAgendaStatus(
  s: string,
): { label: string; tone: "primary" | "success" | "warning" | "danger" | "neutral" } | null {
  if (["atendido", "completed", "finalizado", "concluido"].includes(s)) {
    return { label: "Atendido", tone: "success" };
  }
  if (["em_atendimento", "in_progress", "atendendo"].includes(s)) {
    return { label: "Em atendimento", tone: "primary" };
  }
  if (["cancelado", "cancelled"].includes(s)) {
    return { label: "Cancelado", tone: "danger" };
  }
  if (["agendado", "confirmado", "pending", "scheduled"].includes(s)) {
    return { label: "Aguardando", tone: "warning" };
  }
  return null;
}

function AgentActivityRow({ agent, summary }: { agent: string; summary: string }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-xl bg-surface-container-low border border-outline-variant/20">
      <div className="w-9 h-9 rounded-full bg-primary/15 flex items-center justify-center">
        <MaterialIcon icon="smart_toy" size="sm" className="text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-on-surface">Agente {agent}</p>
        <p className="text-xs text-stone-500">{summary}</p>
      </div>
    </div>
  );
}
