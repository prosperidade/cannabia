"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { StatusPill } from "@/components/status-pill";
import { ApiError, getAiMetrics } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { AiAuditData } from "@/lib/types";

function formatUsd(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(value);
}

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "success") return "ok" as const;
  if (normalized === "error") return "danger" as const;
  if (normalized === "security_blocked") return "warn" as const;
  return "info" as const;
}

export default function AiAuditPage() {
  const router = useRouter();
  const session = useApiSession();
  const [audit, setAudit] = useState<AiAuditData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [daysFilter, setDaysFilter] = useState(30);
  const [limit, setLimit] = useState(10);

  async function loadAudit(
    nextStatus = statusFilter,
    nextDays = daysFilter,
    nextLimit = limit,
  ) {
    setLoading(true);
    setError(null);
    try {
      const data = await getAiMetrics({
        status: nextStatus !== "all" ? nextStatus : undefined,
        days: nextDays > 0 ? nextDays : undefined,
        limit: nextLimit,
      });
      setAudit(data);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar auditoria de IA.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }
    void loadAudit();
  }, [daysFilter, limit, router, session.data, session.loading, statusFilter]);

  if (session.loading || !session.data) {
    return (
      <div className="loading-screen">
        <div className="loading-card">
          <h2>Carregando sessao</h2>
          <p className="lead">Aguardando contexto autenticado do backend.</p>
        </div>
      </div>
    );
  }

  if (!session.data.authenticated) {
    return null;
  }

  const summary = audit?.summary ?? {
    total_execucoes: 0,
    total_tokens: 0,
    total_cost_usd: 0,
    sucessos: 0,
    erros: 0,
    bloqueios: 0,
    tempo_medio_ms: 0,
  };
  const avgCost = summary.total_execucoes ? summary.total_cost_usd / summary.total_execucoes : 0;
  const successRate = summary.total_execucoes ? (summary.sucessos / summary.total_execucoes) * 100 : 0;
  const errorRate = summary.total_execucoes ? (summary.erros / summary.total_execucoes) * 100 : 0;
  const blockedRate = summary.total_execucoes ? (summary.bloqueios / summary.total_execucoes) * 100 : 0;
  const latestLog = audit?.recent_logs[0] ?? null;

  return (
    <AppShell
      session={session.data}
      subtitle="Painel inicial de governança operacional para execuções auditadas da camada de IA."
      title="Auditoria IA"
    >
      <section className="overview-grid">
        <article className="overview-band">
          <span className="meta-label">Execuções</span>
          <h2>{summary.total_execucoes}</h2>
          <p className="lead">Chamadas auditadas para a clínica ativa.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Tokens</span>
          <h2>{summary.total_tokens}</h2>
          <p className="lead">Volume total observado no recorte atual.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Custo</span>
          <h2>{formatUsd(summary.total_cost_usd)}</h2>
          <p className="lead">Estimativa agregada dos logs persistidos.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Tempo médio</span>
          <h2>{Math.round(summary.tempo_medio_ms)} ms</h2>
          <p className="lead">Latência média das execuções registradas.</p>
        </article>
      </section>

      {error ? <div className="inline-error">{error}</div> : null}

      <section className="attendance-toolbar">
        <select
          className="filter-select"
          onChange={(event) => setStatusFilter(event.target.value)}
          value={statusFilter}
        >
          <option value="all">Todos os status</option>
          <option value="success">Success</option>
          <option value="error">Error</option>
          <option value="security_blocked">Security blocked</option>
        </select>
        <select
          className="filter-select"
          onChange={(event) => setDaysFilter(Number(event.target.value))}
          value={daysFilter}
        >
          <option value={7}>Últimos 7 dias</option>
          <option value={30}>Últimos 30 dias</option>
          <option value={90}>Últimos 90 dias</option>
          <option value={0}>Histórico completo</option>
        </select>
        <select
          className="filter-select"
          onChange={(event) => setLimit(Number(event.target.value))}
          value={limit}
        >
          <option value={10}>10 logs</option>
          <option value={25}>25 logs</option>
          <option value={50}>50 logs</option>
        </select>
      </section>

      <section className="analytics-grid">
        <article className="content-card">
          <header className="split-line">
            <div>
              <p className="eyebrow">Saúde operacional</p>
              <h2>Resumo por status</h2>
            </div>
            <button
              className="button-secondary"
              onClick={() => {
                void loadAudit();
              }}
              type="button"
            >
              Recarregar
            </button>
          </header>
          <div className="message-list">
            <article className="message-item">
              <div className="kpi-line">
                <span>Sucessos</span>
                <StatusPill label={String(summary.sucessos)} tone="ok" />
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Erros</span>
                <StatusPill label={String(summary.erros)} tone="danger" />
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Bloqueios</span>
                <StatusPill label={String(summary.bloqueios)} tone="warn" />
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Custo médio</span>
                <strong>{formatUsd(avgCost)}</strong>
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Corte ativo</span>
                <strong>
                  {statusFilter === "all" ? "todos os status" : humanize(statusFilter)} ·{" "}
                  {daysFilter > 0 ? `${daysFilter}d` : "histórico"}
                </strong>
              </div>
            </article>
          </div>
        </article>

        <article className="grid-panel">
          <p className="eyebrow">Leitura rápida</p>
          <h2>Governança prática da IA</h2>
          <p className="lead">
            Esta tela tira a auditoria do backlog abstrato e a traz para o cockpit novo:
            volume, custo, resultado e recência das execuções ficam visíveis sem abrir o
            template legado.
          </p>
          <div className="message-list">
            <article className="message-item">
              <div className="kpi-line">
                <span>Taxa de sucesso</span>
                <strong>{successRate.toFixed(1)}%</strong>
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Taxa de erro</span>
                <strong>{errorRate.toFixed(1)}%</strong>
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Taxa de bloqueio</span>
                <strong>{blockedRate.toFixed(1)}%</strong>
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Última execução</span>
                <strong>{latestLog ? formatDateTime(latestLog.created_at) : "--"}</strong>
              </div>
            </article>
            <article className="message-item">
              <div className="kpi-line">
                <span>Modelo dominante</span>
                <strong>{latestLog?.model ?? "--"}</strong>
              </div>
            </article>
          </div>
        </article>
      </section>

      <article className="grid-panel">
        <header className="split-line">
          <div>
            <p className="eyebrow">Últimos logs</p>
            <h2>Execuções auditadas</h2>
          </div>
        </header>
        {loading ? (
          <div className="inline-empty">Carregando logs de auditoria...</div>
        ) : audit?.recent_logs.length ? (
          <div className="record-list">
            {audit.recent_logs.map((log) => (
              <article className="record-card" key={log.id}>
                <header>
                  <div>
                    <strong>Execução #{log.id}</strong>
                    <p className="lead">
                      {log.patient_id ? `Paciente #${log.patient_id}` : "Paciente não vinculado"} ·{" "}
                      {formatDateTime(log.created_at)}
                    </p>
                  </div>
                  <StatusPill label={humanize(log.status)} tone={statusTone(log.status)} />
                </header>
                <div className="timeline-tags">
                  <span className="mini-pill">{log.endpoint}</span>
                  <span className="mini-pill">{log.model}</span>
                  <span className="mini-pill">{log.total_tokens} tokens</span>
                  <span className="mini-pill">{formatUsd(log.estimated_cost_usd || 0)}</span>
                </div>
                {log.error_message ? <p className="lead">{log.error_message}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <div className="inline-empty">Nenhum log de IA encontrado para esta clínica.</div>
        )}
      </article>
    </AppShell>
  );
}
