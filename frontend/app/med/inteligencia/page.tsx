"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/cn";
import { getClinicalIntelligence } from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  StatCard,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ────────────────────────────────────────────
   AI Clinical Intelligence Analytics Dashboard
   ──────────────────────────────────────────── */

// Fallback mock data used while loading or on error
const FALLBACK_STATS = [
  { icon: "analytics", label: "Total Analises", value: "—", delta: "—", deltaType: "up" as const },
  { icon: "verified", label: "Precisao Media", value: "—", delta: "—", deltaType: "up" as const },
  { icon: "timer", label: "Tempo de Resposta", value: "—", delta: "—", deltaType: "up" as const },
  { icon: "medical_information", label: "Condicoes Identificadas", value: "—", delta: "—", deltaType: "up" as const },
];

const FALLBACK_PERIOD_DATA: { label: string; value: number }[] = [];
const FALLBACK_CONDITIONS: { name: string; count: number; pct: number }[] = [];
const FALLBACK_RISK = [
  { label: "Baixo", pct: 0, color: "bg-emerald-500" },
  { label: "Moderado", pct: 0, color: "bg-amber-500" },
  { label: "Alto", pct: 0, color: "bg-orange-500" },
  { label: "Critico", pct: 0, color: "bg-error" },
];
const FALLBACK_MODELS: { name: string; requests: number; credits: string; cost: string; icon: string }[] = [];
const FALLBACK_EXECUTIONS: { id: string; patient: string; model: string; type: string; confidence: number; date: string; status: string }[] = [];

export default function InteligenciaPage() {
  const [tab, setTab] = useState<"overview" | "executions">("overview");
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(FALLBACK_STATS);
  const [periodData, setPeriodData] = useState(FALLBACK_PERIOD_DATA);
  const [conditions, setConditions] = useState(FALLBACK_CONDITIONS);
  const [risk, setRisk] = useState(FALLBACK_RISK);
  const [models, setModels] = useState(FALLBACK_MODELS);
  const [executions, setExecutions] = useState(FALLBACK_EXECUTIONS);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getClinicalIntelligence();
      const d = res.data as Record<string, unknown>;

      if (Array.isArray(d.stats)) setStats(d.stats as typeof FALLBACK_STATS);
      if (Array.isArray(d.by_period)) setPeriodData(d.by_period as typeof FALLBACK_PERIOD_DATA);
      if (Array.isArray(d.top_conditions)) setConditions(d.top_conditions as typeof FALLBACK_CONDITIONS);
      if (Array.isArray(d.risk_distribution)) setRisk(d.risk_distribution as typeof FALLBACK_RISK);
      if (Array.isArray(d.by_model)) setModels(d.by_model as typeof FALLBACK_MODELS);
      if (Array.isArray(d.recent_executions)) setExecutions(d.recent_executions as typeof FALLBACK_EXECUTIONS);
    } catch {
      // keep fallback data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const maxPeriodValue = periodData.length > 0 ? Math.max(...periodData.map((d) => d.value)) : 1;

  if (loading) {
    return (
      <section className="p-4 md:p-8 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <MaterialIcon icon="hourglass_empty" size="xl" className="text-primary animate-spin" />
          <p className="text-stone-400 text-sm">Carregando dados de inteligencia...</p>
        </div>
      </section>
    );
  }

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Inteligencia Clinica
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            Painel de Inteligencia IA - Monitoramento de desempenho e custos
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setTab(tab === "overview" ? "executions" : "overview")}
          >
            <MaterialIcon icon={tab === "overview" ? "list" : "dashboard"} size="sm" />
            <span className="ml-1">{tab === "overview" ? "Analises Realizadas" : "Visao Geral"}</span>
          </Button>
          <Button size="sm" variant="secondary">
            <MaterialIcon icon="file_download" size="sm" />
            <span className="hidden sm:inline ml-1">Exportar</span>
          </Button>
        </div>
      </div>

      {/* ── Stats Row ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        {stats.map((s) => (
          <StatCard
            key={s.label}
            icon={s.icon}
            label={s.label}
            value={s.value}
            delta={s.delta}
            deltaType={s.deltaType}
          />
        ))}
      </div>

      {tab === "overview" ? (
        <>
          {/* ── Charts Area ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Bar Chart - Analises por Periodo */}
            <div className="lg:col-span-2">
              <Card variant="glass" padding="lg" className="rounded-3xl h-full">
                <div className="flex justify-between items-center mb-8">
                  <div>
                    <h3 className="text-lg font-bold text-on-surface font-headline">
                      Analises por Periodo
                    </h3>
                    <p className="text-sm text-stone-500">Ultimos 6 meses</p>
                  </div>
                  <MaterialIcon icon="bar_chart" className="text-stone-500" />
                </div>
                <div className="flex items-end justify-between gap-3 h-48 px-2">
                  {periodData.map((d) => {
                    const heightPct = (d.value / maxPeriodValue) * 100;
                    return (
                      <div key={d.label} className="flex-1 flex flex-col items-center gap-2">
                        <span className="text-[10px] font-bold text-stone-400">{d.value}</span>
                        <div className="w-full relative h-full flex items-end">
                          <div
                            className="w-full bg-primary/20 hover:bg-primary/40 rounded-t-lg transition-all relative"
                            style={{ height: `${heightPct}%` }}
                          >
                            <div
                              className="absolute bottom-0 w-full bg-primary/60 rounded-t-lg"
                              style={{ height: `${Math.min(heightPct * 0.8, 100)}%` }}
                            />
                          </div>
                        </div>
                        <span className="text-[10px] text-stone-500 font-bold">{d.label}</span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>

            {/* Risk Distribution */}
            <Card variant="glass" padding="lg" className="rounded-3xl">
              <h3 className="text-lg font-bold text-on-surface font-headline mb-2">
                Distribuicao de Risco
              </h3>
              <p className="text-sm text-stone-500 mb-6">Classificacao dos pacientes</p>
              <div className="space-y-4">
                {risk.map((r) => (
                  <div key={r.label} className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-on-surface">{r.label}</span>
                      <span className="text-primary font-bold">{r.pct}%</span>
                    </div>
                    <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
                      <div
                        className={cn("h-full rounded-full transition-all", r.color)}
                        style={{ width: `${r.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 pt-4 border-t border-white/5">
                <div className="flex justify-between text-xs text-stone-500">
                  <span>Total avaliados</span>
                  <span className="font-bold text-on-surface">{stats[0]?.value ?? "—"}</span>
                </div>
              </div>
            </Card>
          </div>

          {/* ── Conditions Ranking + Models ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Horizontal Bar - Condicoes Mais Frequentes */}
            <div className="lg:col-span-2">
              <Card variant="glass" padding="lg" className="rounded-3xl">
                <div className="flex justify-between items-center mb-6">
                  <div>
                    <h3 className="text-lg font-bold text-on-surface font-headline">
                      Condicoes Mais Frequentes
                    </h3>
                    <p className="text-sm text-stone-500">
                      Ranking por frequencia de identificacao
                    </p>
                  </div>
                  <MaterialIcon icon="trending_up" className="text-stone-500" />
                </div>
                <div className="space-y-5">
                  {conditions.map((c) => (
                    <div key={c.name} className="grid grid-cols-12 items-center gap-4">
                      <div className="col-span-3 text-sm font-semibold text-on-surface truncate">
                        {c.name}
                      </div>
                      <div className="col-span-7 h-7 bg-surface-container rounded-full overflow-hidden flex">
                        <div
                          className="h-full bg-primary/60 flex items-center px-3 text-[10px] font-bold text-on-primary rounded-full"
                          style={{ width: `${c.pct}%` }}
                        >
                          {c.pct}%
                        </div>
                      </div>
                      <div className="col-span-2 text-right text-xs text-stone-500">
                        {c.count} casos
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            {/* Models + Cost */}
            <div className="space-y-6">
              <Card variant="glass" padding="md" className="rounded-3xl">
                <div className="flex items-center gap-2 mb-4">
                  <MaterialIcon icon="smart_toy" className="text-primary" />
                  <h4 className="font-bold text-on-surface font-headline">Modelos de Analise</h4>
                </div>
                <div className="space-y-4">
                  {models.map((m) => (
                    <div
                      key={m.name}
                      className="p-4 rounded-xl bg-surface-container/50 border border-white/5 flex items-center gap-4"
                    >
                      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                        <MaterialIcon icon={m.icon} className="text-primary" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-bold text-on-surface">{m.name}</p>
                        <p className="text-[10px] text-stone-500">
                          {m.requests} analises
                        </p>
                      </div>
                      <Badge tone="primary">{m.credits}</Badge>
                    </div>
                  ))}
                </div>
              </Card>

              <Card variant="glass" padding="md" className="rounded-3xl border-primary/10">
                <div className="flex items-center gap-2 mb-4">
                  <MaterialIcon icon="payments" className="text-primary" />
                  <h4 className="font-bold text-on-surface font-headline">Custo de IA</h4>
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-500">Creditos de IA utilizados</span>
                    <span className="font-bold text-on-surface">
                      {models.reduce((acc, m) => acc + (Number(String(m.credits).replace(/[^\d.]/g, "")) || 0), 0).toFixed(1)}M
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-500">Custo estimado</span>
                    <span className="font-bold text-primary text-lg">
                      R$ {models.reduce((acc, m) => acc + (Number(String(m.cost).replace(/[^\d.,]/g, "").replace(",", ".")) || 0), 0).toFixed(2).replace(".", ",")}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-500">Custo medio por analise</span>
                    <span className="font-bold text-on-surface">
                      {models.length > 0
                        ? `R$ ${(models.reduce((acc, m) => acc + (Number(String(m.cost).replace(/[^\d.,]/g, "").replace(",", ".")) || 0), 0) / Math.max(models.reduce((acc, m) => acc + m.requests, 0), 1)).toFixed(2).replace(".", ",")}`
                        : "—"}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </>
      ) : (
        /* ── Executions Log ── */
        <Card variant="glass" padding="sm" className="rounded-3xl overflow-hidden">
          <div className="p-4 md:p-6 border-b border-white/5 flex justify-between items-center">
            <h3 className="font-bold text-on-surface font-headline text-lg">
              Analises Recentes de IA
            </h3>
            <Badge tone="primary">{executions.length} registros</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-surface-container-low">
                <tr>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                    Codigo
                  </th>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                    Paciente
                  </th>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500 hidden md:table-cell">
                    Modelo de Analise
                  </th>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                    Tipo
                  </th>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500 text-center">
                    Confianca
                  </th>
                  <th className="px-4 md:px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500 hidden lg:table-cell">
                    Data
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {executions.map((exe) => (
                  <tr
                    key={exe.id}
                    className="hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <td className="px-4 md:px-6 py-4 text-xs font-mono text-stone-400">
                      {exe.id}
                    </td>
                    <td className="px-4 md:px-6 py-4 text-sm font-semibold text-on-surface">
                      {exe.patient}
                    </td>
                    <td className="px-4 md:px-6 py-4 hidden md:table-cell">
                      <Badge tone="neutral">{exe.model}</Badge>
                    </td>
                    <td className="px-4 md:px-6 py-4">
                      <span className="text-xs text-stone-400 bg-surface-container px-2 py-1 rounded-full">
                        {exe.type}
                      </span>
                    </td>
                    <td className="px-4 md:px-6 py-4 text-center">
                      <span
                        className={cn(
                          "text-sm font-bold",
                          exe.confidence >= 90
                            ? "text-primary"
                            : exe.confidence >= 80
                              ? "text-amber-400"
                              : "text-error",
                        )}
                      >
                        {exe.confidence}%
                      </span>
                    </td>
                    <td className="px-4 md:px-6 py-4 text-xs text-stone-500 hidden lg:table-cell">
                      {exe.date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </section>
  );
}
