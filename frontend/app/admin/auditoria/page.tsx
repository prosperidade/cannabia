"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getAiAudit, type AiAuditPaginatedData, ApiError } from "@/lib/api";
import type { AiAuditLog, AiAuditSummary } from "@/lib/types";
import {
  Card,
  Badge,
  Button,
  StatCard,
  DataTable,
  MaterialIcon,
  ProgressBar,
  type DataTableColumn,
} from "@/components/ui-tw";

/* ================================================================== */
/*  HELPERS                                                            */
/* ================================================================== */

function fmtCurrency(val: number): string {
  return `$${val.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  })}`;
}

function fmtTokens(val: number): string {
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(1)}k`;
  return String(val);
}

function fmtDuration(ms: number): string {
  if (ms >= 1_000) return `${(ms / 1_000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusTone(
  status: string,
): "success" | "danger" | "warning" | "neutral" {
  if (status === "success") return "success";
  if (status === "error") return "danger";
  if (status === "security_blocked") return "warning";
  return "neutral";
}

function statusLabel(status: string): string {
  if (status === "success") return "Sucesso";
  if (status === "error") return "Erro";
  if (status === "security_blocked") return "Bloqueado";
  return status;
}

/* ================================================================== */
/*  FILTER OPTIONS                                                     */
/* ================================================================== */

const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "success", label: "Sucesso" },
  { value: "error", label: "Erro" },
  { value: "security_blocked", label: "Bloqueado" },
];

const DAYS_OPTIONS = [
  { value: 7, label: "7 dias" },
  { value: 30, label: "30 dias" },
  { value: 90, label: "90 dias" },
  { value: 0, label: "Todos" },
];

const LIMIT_OPTIONS = [
  { value: 10, label: "10" },
  { value: 25, label: "25" },
  { value: 50, label: "50" },
];

/* ================================================================== */
/*  COST BREAKDOWN (computed from real data)                           */
/* ================================================================== */

function computeCostBreakdown(logs: AiAuditLog[]) {
  const byModel: Record<string, { cost: number; tokens: number; count: number }> = {};
  const byDay: Record<string, number> = {};

  for (const log of logs) {
    const model = log.model || "unknown";
    if (!byModel[model]) byModel[model] = { cost: 0, tokens: 0, count: 0 };
    byModel[model].cost += log.estimated_cost_usd;
    byModel[model].tokens += log.total_tokens;
    byModel[model].count += 1;

    const day = log.created_at.slice(0, 10);
    byDay[day] = (byDay[day] ?? 0) + log.estimated_cost_usd;
  }

  const totalCost = logs.reduce((s, l) => s + l.estimated_cost_usd, 0);
  const avgCostPerExec =
    logs.length > 0 ? totalCost / logs.length : 0;

  const sortedDays = Object.entries(byDay).sort(([a], [b]) =>
    a.localeCompare(b),
  );

  return { byModel, sortedDays, avgCostPerExec, totalCost };
}

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function AuditoriaPage() {
  useApiSession();

  /* ── State ── */
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AiAuditPaginatedData | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const [statusFilter, setStatusFilter] = useState("");
  const [daysFilter, setDaysFilter] = useState(30);
  const [limitFilter, setLimitFilter] = useState(25);

  /* ── Fetch ── Sprint 3 Page-Migration: usa envelope `Paginated<AiAuditLog>` */
  const fetchData = useCallback(
    async (opts?: { append?: boolean }) => {
      setLoading(true);
      setError(null);
      try {
        const nextOffset = opts?.append ? offset : 0;
        const result = await getAiAudit({
          status: statusFilter || undefined,
          days: daysFilter || undefined,
          limit: limitFilter,
          offset: nextOffset,
        });
        if (opts?.append && data) {
          // Anexa ao paginated envelope dos recent_logs
          setData({
            ...result,
            recent_logs: {
              ...result.recent_logs,
              items: [...data.recent_logs.items, ...result.recent_logs.items],
            },
          });
        } else {
          setData(result);
        }
        setHasMore(result.recent_logs.has_more);
        setOffset(nextOffset + result.recent_logs.items.length);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : "Falha ao carregar metricas de IA.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [statusFilter, daysFilter, limitFilter, offset, data],
  );

  // Filtros resetam paginacao (fetchData(opts=undefined) zera offset).
  useEffect(() => {
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, daysFilter, limitFilter]);

  /* ── Derived values ── */
  const summary: AiAuditSummary | null = data?.summary ?? null;
  const logs: AiAuditLog[] = data?.recent_logs.items ?? [];

  const successRate = summary
    ? summary.total_execucoes > 0
      ? ((summary.sucessos / summary.total_execucoes) * 100).toFixed(1)
      : "0"
    : "--";

  const errorRate = summary
    ? summary.total_execucoes > 0
      ? ((summary.erros / summary.total_execucoes) * 100).toFixed(1)
      : "0"
    : "--";

  const blockedRate = summary
    ? summary.total_execucoes > 0
      ? ((summary.bloqueios / summary.total_execucoes) * 100).toFixed(1)
      : "0"
    : "--";

  const costBreakdown = useMemo(
    () => computeCostBreakdown(logs),
    [logs],
  );

  /* ── Table columns ── */
  const columns: DataTableColumn[] = useMemo(
    () => [
      {
        key: "created_at",
        label: "Data/Hora",
        sortable: true,
        render: (val) => (
          <span className="text-stone-400 font-medium text-sm">
            {fmtDate(String(val))}
          </span>
        ),
      },
      {
        key: "endpoint",
        label: "Servico",
        sortable: true,
        render: (val) => (
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary" />
            <span className="text-on-surface font-semibold text-sm">
              {String(val)}
            </span>
          </div>
        ),
      },
      {
        key: "model",
        label: "Modelo de Analise",
        sortable: true,
        render: (val) => {
          const model = String(val);
          const isGpt = model.toLowerCase().includes("gpt");
          return (
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  isGpt ? "bg-primary" : "bg-secondary",
                )}
              />
              <span className="text-sm">{model}</span>
            </div>
          );
        },
      },
      {
        key: "total_tokens",
        label: "Creditos de IA",
        sortable: true,
        render: (val) => (
          <span className="text-on-surface-variant text-sm font-mono">
            {fmtTokens(Number(val))}
          </span>
        ),
      },
      {
        key: "estimated_cost_usd",
        label: "Custo",
        sortable: true,
        render: (val) => (
          <span className="text-on-surface text-sm font-mono">
            {fmtCurrency(Number(val))}
          </span>
        ),
      },
      {
        key: "status",
        label: "Status",
        sortable: true,
        render: (_val, row) => {
          const log = row as unknown as AiAuditLog;
          return (
            <Badge tone={statusTone(log.status)}>{statusLabel(log.status)}</Badge>
          );
        },
      },
      {
        key: "patient_id",
        label: "Paciente",
        render: (val) => (
          <span className="text-stone-500 text-sm">
            {val ? `Cod. ${val}` : "--"}
          </span>
        ),
      },
    ],
    [],
  );

  const tableData = useMemo(
    () => logs as unknown as Record<string, unknown>[],
    [logs],
  );

  /* ── Max bar height for chart ── */
  const maxDayCost = useMemo(() => {
    if (costBreakdown.sortedDays.length === 0) return 1;
    return Math.max(...costBreakdown.sortedDays.map(([, v]) => v), 0.01);
  }, [costBreakdown.sortedDays]);

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-on-surface mb-2">
            Auditoria de <span className="text-primary">IA</span>
            <span className="text-on-surface-variant font-bold text-lg md:text-xl ml-2">
              e Controle de Custos
            </span>
          </h1>
          <p className="text-on-surface-variant max-w-xl">
            Monitoramento de custos, uso de IA e precisao dos modelos de
            analise em producao.
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <Button variant="secondary" icon="download" size="sm">
            Exportar PDF
          </Button>
          <Button variant="primary" icon="ios_share" size="sm">
            Exportar CSV
          </Button>
        </div>
      </header>

      {/* ── Filters ── */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Status filter */}
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm">
          <MaterialIcon icon="filter_list" size="sm" className="text-primary" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-transparent border-none focus:ring-0 text-on-surface cursor-pointer font-medium text-sm"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Days filter */}
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm">
          <MaterialIcon
            icon="calendar_month"
            size="sm"
            className="text-primary"
          />
          <select
            value={daysFilter}
            onChange={(e) => setDaysFilter(Number(e.target.value))}
            className="bg-transparent border-none focus:ring-0 text-on-surface cursor-pointer font-medium text-sm"
          >
            {DAYS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Limit filter */}
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm">
          <MaterialIcon icon="list" size="sm" className="text-primary" />
          <select
            value={limitFilter}
            onChange={(e) => setLimitFilter(Number(e.target.value))}
            className="bg-transparent border-none focus:ring-0 text-on-surface cursor-pointer font-medium text-sm"
          >
            {LIMIT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.value} registros
              </option>
            ))}
          </select>
        </div>

        <Button
          variant="ghost"
          icon="refresh"
          size="sm"
          onClick={() => void fetchData()}
          loading={loading}
        >
          Atualizar
        </Button>
      </div>

      {/* ── Error state ── */}
      {error && (
        <Card variant="outline" padding="md" className="border-error/30">
          <div className="flex items-center gap-3">
            <MaterialIcon icon="error" className="text-error" />
            <div>
              <p className="text-sm font-bold text-error">
                Erro ao carregar dados
              </p>
              <p className="text-xs text-on-surface-variant">{error}</p>
            </div>
            <Button
              variant="danger"
              size="sm"
              className="ml-auto"
              onClick={() => void fetchData()}
            >
              Tentar novamente
            </Button>
          </div>
        </Card>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !data && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="glass-panel rounded-2xl p-5 h-28 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* ── KPIs ── */}
      {summary && (
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            icon="play_circle"
            label="Total de Analises"
            value={summary.total_execucoes.toLocaleString("pt-BR")}
          />
          <StatCard
            icon="memory"
            label="Creditos de IA Usados"
            value={fmtTokens(summary.total_tokens)}
          />
          <StatCard
            icon="payments"
            label="Custo Total (USD)"
            value={fmtCurrency(summary.total_cost_usd)}
          />
          <StatCard
            icon="timer"
            label="Tempo de Resposta"
            value={fmtDuration(summary.tempo_medio_ms)}
          />
        </section>
      )}

      {/* ── Rates ── */}
      {summary && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card variant="glass" padding="md">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-stone-500 uppercase tracking-widest">
                Taxa de Sucesso
              </span>
              <Badge tone="success">{successRate}%</Badge>
            </div>
            <ProgressBar
              value={Number(successRate)}
              variant="success"
              glow
            />
            <p className="text-xs text-stone-500 mt-2">
              {summary.sucessos} de {summary.total_execucoes} analises
            </p>
          </Card>

          <Card variant="glass" padding="md">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-stone-500 uppercase tracking-widest">
                Taxa de Erros
              </span>
              <Badge tone="danger">{errorRate}%</Badge>
            </div>
            <ProgressBar value={Number(errorRate)} variant="danger" />
            <p className="text-xs text-stone-500 mt-2">
              {summary.erros} erros registrados
            </p>
          </Card>

          <Card variant="glass" padding="md">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-stone-500 uppercase tracking-widest">
                Bloqueios Seguranca
              </span>
              <Badge tone="warning">{blockedRate}%</Badge>
            </div>
            <ProgressBar value={Number(blockedRate)} variant="warning" />
            <p className="text-xs text-stone-500 mt-2">
              {summary.bloqueios} bloqueios de seguranca
            </p>
          </Card>
        </section>
      )}

      {/* ── Cost Breakdown & Chart ── */}
      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Cost by model */}
          <Card variant="glass" padding="md" className="lg:col-span-1">
            <h3 className="text-lg font-bold font-headline text-on-surface mb-6">
              Custo por Modelo
            </h3>
            <div className="space-y-5">
              {Object.entries(costBreakdown.byModel).map(
                ([model, info]) => {
                  const pct =
                    costBreakdown.totalCost > 0
                      ? (info.cost / costBreakdown.totalCost) * 100
                      : 0;
                  const isGpt = model.toLowerCase().includes("gpt");
                  return (
                    <div key={model} className="space-y-2">
                      <div className="flex justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              "w-2.5 h-2.5 rounded-full",
                              isGpt ? "bg-primary" : "bg-secondary",
                            )}
                          />
                          <span className="text-on-surface font-medium">
                            {model}
                          </span>
                        </div>
                        <span className="text-on-surface font-mono">
                          {fmtCurrency(info.cost)}
                        </span>
                      </div>
                      <ProgressBar
                        value={pct}
                        variant={isGpt ? "primary" : "success"}
                        size="sm"
                      />
                      <div className="flex justify-between text-[10px] text-stone-500">
                        <span>{info.count} analises</span>
                        <span>{fmtTokens(info.tokens)} creditos</span>
                      </div>
                    </div>
                  );
                },
              )}

              {Object.keys(costBreakdown.byModel).length === 0 && (
                <p className="text-sm text-stone-500">Sem dados disponiveis.</p>
              )}
            </div>

            {/* Extra stats */}
            <div className="mt-6 pt-6 border-t border-white/5 space-y-3">
              <div className="flex justify-between text-xs">
                <span className="text-stone-500">Custo medio / analise</span>
                <span className="text-on-surface font-mono font-bold">
                  {fmtCurrency(costBreakdown.avgCostPerExec)}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-stone-500">Projecao mensal</span>
                <span className="text-primary font-mono font-bold">
                  {summary
                    ? fmtCurrency(
                        (summary.total_cost_usd /
                          Math.max(daysFilter || 30, 1)) *
                          30,
                      )
                    : "--"}
                </span>
              </div>
            </div>
          </Card>

          {/* Cost trend chart */}
          <Card variant="glass" padding="md" className="lg:col-span-2">
            <div className="flex justify-between items-start mb-8">
              <div>
                <h3 className="text-lg font-bold font-headline text-on-surface mb-1">
                  Evolucao de Custos
                </h3>
                <p className="text-stone-500 text-xs">
                  Custo diario nos ultimos {daysFilter || "N"} dias
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-primary" />
                <span className="text-xs text-stone-400">Custo (USD)</span>
              </div>
            </div>

            {costBreakdown.sortedDays.length > 0 ? (
              <>
                <div className="relative h-48 flex items-end justify-between gap-1 overflow-x-auto">
                  {costBreakdown.sortedDays.map(([day, cost]) => {
                    const heightPct = (cost / maxDayCost) * 100;
                    return (
                      <div
                        key={day}
                        className="flex-1 min-w-[12px] group relative"
                      >
                        <div
                          className="w-full bg-primary/20 rounded-t-sm hover:bg-primary/40 transition-all"
                          style={{ height: `${Math.max(heightPct, 2)}%` }}
                        />
                        {/* Tooltip */}
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-stone-900 text-[10px] p-1.5 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-10 pointer-events-none">
                          {day}: {fmtCurrency(cost)}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="flex justify-between mt-3 text-[10px] text-stone-600 font-bold uppercase tracking-widest">
                  <span>
                    {costBreakdown.sortedDays[0]?.[0]?.slice(5) ?? ""}
                  </span>
                  <span>
                    {costBreakdown.sortedDays[
                      costBreakdown.sortedDays.length - 1
                    ]?.[0]?.slice(5) ?? ""}
                  </span>
                </div>
              </>
            ) : (
              <div className="h-48 flex items-center justify-center text-stone-500 text-sm">
                Sem dados de custo para o periodo.
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Health / Status counts ── */}
      {summary && (
        <Card variant="glass" padding="md">
          <h3 className="text-lg font-bold font-headline text-on-surface mb-4">
            Status de Saude do Sistema
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-3 p-4 bg-white/5 rounded-xl">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                <MaterialIcon
                  icon="check_circle"
                  filled
                  className="text-emerald-400"
                />
              </div>
              <div>
                <p className="text-xl font-bold text-on-surface font-headline">
                  {summary.sucessos}
                </p>
                <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                  Sucessos
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 p-4 bg-white/5 rounded-xl">
              <div className="w-10 h-10 rounded-lg bg-error/10 flex items-center justify-center">
                <MaterialIcon icon="error" filled className="text-error" />
              </div>
              <div>
                <p className="text-xl font-bold text-on-surface font-headline">
                  {summary.erros}
                </p>
                <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                  Erros
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 p-4 bg-white/5 rounded-xl">
              <div className="w-10 h-10 rounded-lg bg-amber-400/10 flex items-center justify-center">
                <MaterialIcon
                  icon="shield"
                  filled
                  className="text-amber-400"
                />
              </div>
              <div>
                <p className="text-xl font-bold text-on-surface font-headline">
                  {summary.bloqueios}
                </p>
                <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                  Bloqueios
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 p-4 bg-white/5 rounded-xl">
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                <MaterialIcon
                  icon="speed"
                  filled
                  className="text-primary"
                />
              </div>
              <div>
                <p className="text-xl font-bold text-on-surface font-headline">
                  {fmtDuration(summary.tempo_medio_ms)}
                </p>
                <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                  Tempo Medio
                </p>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* ── Budget Alert ── */}
      {summary && summary.total_cost_usd > 0 && (
        <Card variant="outline" padding="md" className="border-primary/20">
          <div className="flex flex-col md:flex-row items-start md:items-center gap-4">
            <div className="bg-primary/20 p-2 rounded-full shrink-0">
              <MaterialIcon
                icon="warning"
                filled
                className="text-primary"
              />
            </div>
            <div className="flex-1">
              <p className="text-sm font-bold text-on-surface">
                Alerta de Orcamento
              </p>
              <p className="text-xs text-stone-400 mt-1">
                Projecao mensal:{" "}
                <span className="text-primary font-bold">
                  {fmtCurrency(
                    (summary.total_cost_usd / Math.max(daysFilter || 30, 1)) *
                      30,
                  )}
                </span>
                . Monitore o consumo e ajuste limites conforme necessario.
              </p>
            </div>
            <Button variant="secondary" size="sm" icon="tune">
              Configurar Limites
            </Button>
          </div>
        </Card>
      )}

      {/* ── Recent Executions Log Table ── */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold font-headline text-on-surface">
            Analises Recentes
          </h3>
          <span className="text-xs text-stone-500">
            {logs.length} registro{logs.length !== 1 ? "s" : ""}
            {hasMore ? " (+)" : ""}
          </span>
        </div>

        {/* Desktop table */}
        <div className="hidden md:block">
          <DataTable
            columns={columns}
            data={tableData}
            emptyMessage={
              loading
                ? "Carregando..."
                : "Nenhuma analise encontrada para os filtros selecionados."
            }
          />
        </div>

        {/* Mobile cards */}
        <div className="md:hidden space-y-3">
          {logs.length === 0 && !loading && (
            <Card variant="glass" padding="md">
              <p className="text-sm text-stone-500 text-center">
                Nenhuma analise encontrada.
              </p>
            </Card>
          )}
          {logs.map((log) => (
            <Card
              key={log.id}
              variant="glass"
              padding="sm"
              className={cn(
                "border-l-2",
                log.status === "success" && "border-l-emerald-400",
                log.status === "error" && "border-l-error",
                log.status === "security_blocked" && "border-l-amber-400",
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-surface-container-highest flex items-center justify-center">
                    <MaterialIcon
                      icon="smart_toy"
                      size="sm"
                      className="text-primary"
                    />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-on-surface">
                      {log.endpoint}
                    </p>
                    <p className="text-[10px] text-stone-500">
                      {fmtDate(log.created_at)} - {log.model}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-primary font-mono">
                    {fmtCurrency(log.estimated_cost_usd)}
                  </p>
                  <p className="text-[10px] text-stone-500">
                    {fmtTokens(log.total_tokens)} creditos
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <Badge tone={statusTone(log.status)}>
                  {statusLabel(log.status)}
                </Badge>
                {log.patient_id && (
                  <span className="text-[10px] text-stone-500">
                    Cod. paciente {log.patient_id}
                  </span>
                )}
              </div>
              {log.error_message && (
                <p className="text-xs text-error mt-2 p-2 bg-error/5 rounded-lg">
                  {log.error_message}
                </p>
              )}
            </Card>
          ))}
        </div>

        {hasMore && (
          <div className="mt-4 flex justify-center">
            <Button
              variant="secondary"
              size="sm"
              icon="expand_more"
              loading={loading}
              onClick={() => void fetchData({ append: true })}
            >
              Carregar mais
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
