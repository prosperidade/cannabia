"use client";

import { useSystemStatus } from "@/lib/use-system-status";
import { cn } from "@/lib/cn";
import {
  StatCard,
  Badge,
  Card,
  Button,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ── Helpers ── */

const statusColor: Record<string, string> = {
  healthy: "bg-emerald-500",
  degraded: "bg-amber-500",
  unhealthy: "bg-error",
  offline: "bg-stone-600",
  unknown: "bg-stone-600",
};

const statusLabel: Record<string, string> = {
  healthy: "Online",
  degraded: "Degradado",
  unhealthy: "Indisponivel",
  offline: "Offline",
  unknown: "Verificando...",
};

const statusBadgeTone: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  healthy: "success",
  degraded: "warning",
  unhealthy: "danger",
  offline: "neutral",
  unknown: "neutral",
};

const componentIcons: Record<string, string> = {
  database: "database",
  cache: "memory",
  whatsapp: "chat",
  ai_pipeline: "psychology",
};

const componentLabels: Record<string, string> = {
  database: "Banco de Dados",
  cache: "Cache (Redis)",
  whatsapp: "WhatsApp API",
  ai_pipeline: "Analise Inteligente",
};

/* ── Mock data for items not yet from API ── */

const MOCK_KPIS = {
  total_tenants: 48,
  total_users: 312,
  ai_executions: 12847,
  platform_uptime: "99.97%",
};

const MOCK_FLAGS = [
  { name: "Onboarding de Tenants (5.2)", status: "Em desenvolvimento" },
  { name: "Billing / Planos (5.3)", status: "Em desenvolvimento" },
  { name: "Templates de Campanhas (5.4)", status: "Planejado" },
  { name: "Modo Degradacao Graceful (5.5)", status: "Frontend pronto" },
  { name: "RAG Multi-tenant (5.6)", status: "Planejado" },
];

const MOCK_EVENTS = [
  {
    id: 1,
    type: "security" as const,
    title: "Alerta de Seguranca",
    description: "Tentativa de acesso nao autorizado bloqueada pelo firewall.",
    time: "2 min atras",
  },
  {
    id: 2,
    type: "scaling" as const,
    title: "Auto-scaling Ativado",
    description: "Cluster de inferencia adicionou 2 nos por demanda elevada.",
    time: "14 min atras",
  },
  {
    id: 3,
    type: "maintenance" as const,
    title: "Manutencao Concluida",
    description: "Re-indexacao do banco de dados PostgreSQL finalizada com sucesso.",
    time: "1 hora atras",
  },
  {
    id: 4,
    type: "deploy" as const,
    title: "Deploy Realizado",
    description: "Nova versao v3.4.2 publicada no ambiente de producao.",
    time: "3 horas atras",
  },
];

const eventDotColor: Record<string, string> = {
  security: "bg-error",
  scaling: "bg-primary",
  maintenance: "bg-stone-500",
  deploy: "bg-secondary",
};

export default function AdminOverviewPage() {
  const status = useSystemStatus();

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-10">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-primary mb-2">
            Administracao
          </p>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tight text-on-surface">
            Painel Administrativo
          </h1>
          <p className="text-on-surface-variant mt-1 text-sm max-w-lg">
            Visao Geral do Sistema - Monitoramento e gestao da infraestrutura Cannab&apos;IA.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            icon="refresh"
            onClick={status.refresh}
          >
            Atualizar
          </Button>
          <Button variant="primary" size="sm" icon="build">
            Manutencao
          </Button>
        </div>
      </header>

      {/* ── System Health Overview ── */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-bold font-headline flex items-center gap-2 text-on-surface">
            <MaterialIcon icon="analytics" className="text-primary" />
            Vitalidade do Sistema em Tempo Real
          </h2>
          <span
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-full text-[10px] font-bold uppercase tracking-widest border",
              status.overall === "healthy"
                ? "bg-primary/10 text-primary border-primary/20"
                : status.overall === "degraded"
                  ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  : "bg-error/10 text-error border-error/20",
            )}
          >
            <span
              className={cn(
                "w-2 h-2 rounded-full",
                statusColor[status.overall] ?? "bg-stone-600",
                status.overall === "healthy" && "shadow-[0_0_8px_rgba(16,185,129,0.6)]",
              )}
            />
            {statusLabel[status.overall] ?? "Verificando..."}{" "}
            {status.overall === "healthy" && "- 99.98% UP"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.keys(status.components).length > 0
            ? Object.entries(status.components).map(([name, comp]) => (
                <Card key={name} variant="glass" padding="md" className="relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -mr-12 -mt-12 blur-2xl group-hover:bg-primary/10 transition-colors" />
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <MaterialIcon
                          icon={componentIcons[name] ?? "settings"}
                          className="text-primary"
                        />
                      </div>
                      <span className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                        {componentLabels[name] ?? name}
                      </span>
                    </div>
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
                        comp.status === "healthy"
                          ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"
                          : comp.status === "degraded"
                            ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)] animate-pulse"
                            : "bg-error shadow-[0_0_8px_rgba(255,180,171,0.6)] animate-pulse",
                      )}
                    />
                  </div>
                  <div className="text-2xl font-bold font-headline text-on-surface mb-1">
                    {comp.latency_ms != null ? `${comp.latency_ms}ms` : "--"}
                  </div>
                  <Badge tone={statusBadgeTone[comp.status] ?? "neutral"}>
                    {statusLabel[comp.status] ?? "Verificando..."}
                  </Badge>
                </Card>
              ))
            : /* Fallback mock cards when no components data */
              ["Camada de Servicos", "Banco de Dados", "Analise Inteligente", "Cache"].map((label) => (
                <Card key={label} variant="glass" padding="md" className="relative overflow-hidden group">
                  <div className="absolute top-0 right-0 w-24 h-24 bg-primary/5 rounded-full -mr-12 -mt-12 blur-2xl" />
                  <div className="flex justify-between items-start mb-4">
                    <span className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">
                      {label}
                    </span>
                    <span className="h-2.5 w-2.5 rounded-full bg-stone-600" />
                  </div>
                  <div className="text-2xl font-bold font-headline text-stone-500 mb-1">--</div>
                  <Badge tone="neutral">Verificando...</Badge>
                </Card>
              ))}
        </div>
        {status.lastChecked && (
          <p className="text-[11px] text-stone-500 mt-3">
            Ultima verificacao: {status.lastChecked.toLocaleTimeString("pt-BR")}
          </p>
        )}
      </section>

      {/* ── Platform KPIs ── */}
      <section>
        <h2 className="text-lg font-bold font-headline flex items-center gap-2 text-on-surface mb-4">
          <MaterialIcon icon="query_stats" className="text-primary" />
          Indicadores da Plataforma
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon="apartment" label="Total Organizacoes" value={MOCK_KPIS.total_tenants} />
          <StatCard icon="group" label="Total Usuarios" value={MOCK_KPIS.total_users} />
          <StatCard
            icon="psychology"
            label="Analises Realizadas"
            value={MOCK_KPIS.ai_executions.toLocaleString("pt-BR")}
            delta="+12%"
            deltaType="up"
          />
          <StatCard icon="timer" label="Uptime Plataforma" value={MOCK_KPIS.platform_uptime} />
        </div>
      </section>

      {/* ── Neural Resource Load ── */}
      <section>
        <Card variant="glass" padding="lg">
          <h2 className="text-lg font-bold font-headline flex items-center gap-2 text-on-surface mb-6">
            <MaterialIcon icon="memory" className="text-secondary" />
            Carga de Recursos
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-on-surface-variant">Uso de IA</span>
                <span className="text-primary font-bold">72%</span>
              </div>
              <ProgressBar value={72} variant="primary" glow />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-on-surface-variant">Processamento</span>
                <span className="text-secondary font-bold">45%</span>
              </div>
              <ProgressBar value={45} variant="success" />
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium">
                <span className="text-on-surface-variant">Memoria do Cluster</span>
                <span className="text-primary font-bold">89%</span>
              </div>
              <ProgressBar value={89} variant="warning" glow />
            </div>
          </div>
        </Card>
      </section>

      {/* ── Bottom Grid: Feature Flags + Events ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feature Flags */}
        <Card variant="glass" padding="md">
          <h3 className="text-lg font-bold font-headline flex items-center gap-2 text-on-surface mb-6">
            <MaterialIcon icon="flag" className="text-primary" />
            Funcionalidades do Sistema
          </h3>
          <div className="space-y-3">
            {MOCK_FLAGS.map((flag) => (
              <div
                key={flag.name}
                className="flex items-center justify-between py-2 px-3 rounded-xl bg-white/[0.02] border border-white/5"
              >
                <span className="text-sm font-medium text-on-surface">{flag.name}</span>
                <Badge
                  tone={
                    flag.status === "Frontend pronto"
                      ? "success"
                      : flag.status === "Em desenvolvimento"
                        ? "info"
                        : "neutral"
                  }
                >
                  {flag.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        {/* System Event Log */}
        <Card variant="glass" padding="md">
          <h3 className="text-lg font-bold font-headline flex items-center gap-2 text-on-surface mb-6">
            <MaterialIcon icon="history" className="text-primary" />
            Log de Eventos do Sistema
          </h3>
          <div className="space-y-4">
            {MOCK_EVENTS.map((event, idx) => (
              <div key={event.id} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div
                    className={cn(
                      "w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0",
                      eventDotColor[event.type] ?? "bg-stone-500",
                    )}
                  />
                  {idx < MOCK_EVENTS.length - 1 && (
                    <div className="w-px flex-1 bg-white/10 mt-2" />
                  )}
                </div>
                <div className="pb-4">
                  <p className="text-xs font-bold uppercase tracking-widest mb-1 text-on-surface">
                    {event.title}
                  </p>
                  <p className="text-sm text-on-surface-variant leading-relaxed">
                    {event.description}
                  </p>
                  <p className="text-[10px] text-stone-500 mt-1 italic uppercase">
                    {event.time}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
