"use client";

import { Card, MaterialIcon, Badge } from "@/components/ui-tw";
import { useApiSession } from "@/lib/use-api-session";

/**
 * Pagina de Acompanhamento — cuidado continuo dos pacientes entre
 * consultas, alimentado pelos agentes IA (Triagem, FollowUp,
 * Regulatorio).
 *
 * Esta versao e um SKELETON com 5 cards visuais. A populacao real
 * com endpoints (pacientes em risco, follow-ups pendentes, eventos
 * adversos abertos, etc.) entra na proxima task.
 *
 * Visivel para: Medico, Recepcao, AdminClinica, Admin global.
 */
export default function AcompanhamentoPage() {
  const { data: session } = useApiSession();
  const userName = session?.user?.username ?? "";

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

      {/* ── KPIs do dia ─────────────────────────────────────────── */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard
          icon="warning"
          tone="danger"
          label="Pacientes em risco"
          value="—"
          hint="red flags detectados pelo agente Triagem"
        />
        <KpiCard
          icon="schedule"
          tone="warning"
          label="Follow-ups pendentes"
          value="—"
          hint="aguardando resposta D+3, D+7 ou D+15"
        />
        <KpiCard
          icon="medical_services"
          tone="info"
          label="Triagens em andamento"
          value="—"
          hint="anamneses sendo coletadas via WhatsApp"
        />
        <KpiCard
          icon="report"
          tone="danger"
          label="Eventos adversos abertos"
          value="—"
          hint="sem avaliacao do medico ainda"
        />
      </section>

      {/* ── Alertas ────────────────────────────────────────────── */}
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

      {/* ── Mensagens automaticas ──────────────────────────────── */}
      <Card padding="lg">
        <div className="flex items-start justify-between mb-5 gap-3">
          <SectionHeader
            icon="auto_awesome"
            title="Atividade dos agentes hoje"
            desc="Transparencia: o que os agentes IA fizeram autonomamente."
          />
          <Badge tone="info">Ultimas 24h</Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AgentActivityRow agent="Triagem"      summary="—" />
          <AgentActivityRow agent="Anamnese"     summary="—" />
          <AgentActivityRow agent="FollowUp"     summary="—" />
          <AgentActivityRow agent="Regulatorio"  summary="—" />
        </div>
      </Card>

      {/* ── Tabela de pacientes em acompanhamento ───────────────── */}
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
        </p>
      )}
    </div>
  );
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
