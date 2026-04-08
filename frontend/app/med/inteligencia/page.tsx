"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
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
   TODO: replace all mock data with real API calls.
   ──────────────────────────────────────────── */

// TODO: fetch from API
const MOCK_STATS = [
  { icon: "analytics", label: "Total Analises", value: "2.847", delta: "+128", deltaType: "up" as const },
  { icon: "verified", label: "Precisao Media", value: "94.2%", delta: "+1.8%", deltaType: "up" as const },
  { icon: "timer", label: "Tempo de Resposta", value: "3.2s", delta: "-0.5s", deltaType: "up" as const },
  { icon: "medical_information", label: "Condicoes Identificadas", value: "186", delta: "+23", deltaType: "up" as const },
];

// TODO: fetch from API
const MOCK_PERIOD_DATA = [
  { label: "Jan", value: 320 },
  { label: "Fev", value: 450 },
  { label: "Mar", value: 380 },
  { label: "Abr", value: 520 },
  { label: "Mai", value: 610 },
  { label: "Jun", value: 490 },
];

// TODO: fetch from API
const MOCK_CONDITIONS = [
  { name: "Dor Cronica", count: 342, pct: 85 },
  { name: "Ansiedade", count: 289, pct: 72 },
  { name: "Insonia", count: 198, pct: 52 },
  { name: "Espasticidade", count: 154, pct: 40 },
  { name: "Epilepsia", count: 112, pct: 28 },
];

// TODO: fetch from API
const MOCK_RISK = [
  { label: "Baixo", pct: 42, color: "bg-emerald-500" },
  { label: "Moderado", pct: 31, color: "bg-amber-500" },
  { label: "Alto", pct: 19, color: "bg-orange-500" },
  { label: "Critico", pct: 8, color: "bg-error" },
];

// TODO: fetch from API
const MOCK_MODELS = [
  { name: "GPT-4", requests: 1842, credits: "4.2M", cost: "R$ 312,00", icon: "smart_toy" },
  { name: "Gemini Pro", requests: 1005, credits: "2.8M", cost: "R$ 156,00", icon: "auto_awesome" },
];

// TODO: fetch from API
const MOCK_EXECUTIONS = [
  { id: "AN-001", patient: "Elena Sterling", model: "GPT-4", type: "Anamnese", confidence: 96, date: "07/04/2026 14:32", status: "success" },
  { id: "AN-002", patient: "Carlos Mendes", model: "Gemini", type: "Plano Terapeutico", confidence: 91, date: "07/04/2026 13:18", status: "success" },
  { id: "AN-003", patient: "Ana Beatriz", model: "GPT-4", type: "Interacao Medicamentosa", confidence: 88, date: "07/04/2026 11:45", status: "warning" },
  { id: "AN-004", patient: "Roberto Silva", model: "GPT-4", type: "Anamnese", confidence: 94, date: "06/04/2026 16:22", status: "success" },
  { id: "AN-005", patient: "Lucia Fernandes", model: "Gemini", type: "Revisao Laboratorial", confidence: 79, date: "06/04/2026 10:05", status: "warning" },
];

const maxPeriodValue = Math.max(...MOCK_PERIOD_DATA.map((d) => d.value));

export default function InteligenciaPage() {
  const [tab, setTab] = useState<"overview" | "executions">("overview");

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
        {MOCK_STATS.map((s) => (
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
                  {MOCK_PERIOD_DATA.map((d) => {
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
                {MOCK_RISK.map((r) => (
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
                  <span className="font-bold text-on-surface">2.847</span>
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
                  {MOCK_CONDITIONS.map((c) => (
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
                  {MOCK_MODELS.map((m) => (
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
                    <span className="font-bold text-on-surface">7.0M</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-500">Custo estimado</span>
                    <span className="font-bold text-primary text-lg">R$ 468,00</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-stone-500">Custo medio por analise</span>
                    <span className="font-bold text-on-surface">R$ 0,16</span>
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
            <Badge tone="primary">{MOCK_EXECUTIONS.length} registros</Badge>
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
                {MOCK_EXECUTIONS.map((exe) => (
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
