"use client";

import { useEffect, useState } from "react";

import { Card, MaterialIcon, Badge } from "@/components/ui-tw";
import {
  getAcompanhamentoOverview,
  type AcompanhamentoOverview,
} from "@/lib/api";
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
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErrorMsg(null);
    getAcompanhamentoOverview()
      .then((data) => {
        if (!alive) return;
        setOverview(data);
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

      {/* Lista de pacientes em acompanhamento ativo — proxima sprint */}
      <Card padding="lg">
        <SectionHeader
          icon="favorite"
          title="Pacientes em acompanhamento ativo"
          desc="Lista dos pacientes com tratamento em andamento."
        />
        <EmptyState
          icon="hourglass_empty"
          title="Em construcao"
          subtitle="A listagem com ultimo contato, dia do tratamento e outcome classificado vem na proxima sprint."
        />
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
