"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/cn";
import { getOrgReports } from "@/lib/api";
import {
  Card,
  StatCard,
  Button,
  Badge,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

type TabKey = "atendimentos" | "financeiro" | "pacientes" | "ia";
type PeriodKey = "7d" | "30d" | "90d" | "12m";
type ChartPoint = { label: string; a: number; b: number };

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "atendimentos", label: "Atendimentos", icon: "clinical_notes" },
  { key: "financeiro", label: "Financeiro", icon: "payments" },
  { key: "pacientes", label: "Pacientes", icon: "group" },
  { key: "ia", label: "Analise Inteligente", icon: "auto_awesome" },
];

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: "7d", label: "7 dias" },
  { key: "30d", label: "30 dias" },
  { key: "90d", label: "90 dias" },
  { key: "12m", label: "12 meses" },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function RelatoriosPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("atendimentos");
  const [period, setPeriod] = useState<PeriodKey>("30d");
  const [loading, setLoading] = useState(true);

  // Chart data per tab
  const [atendimentosChart, setAtendimentosChart] = useState<ChartPoint[]>([]);
  const [financeiroChart, setFinanceiroChart] = useState<ChartPoint[]>([]);
  const [pacientesChart, setPacientesChart] = useState<ChartPoint[]>([]);
  const [iaChart, setIaChart] = useState<ChartPoint[]>([]);

  // Side-panel data
  const [doctorRanking, setDoctorRanking] = useState<{ name: string; count: number; pct: number }[]>([]);
  const [statusDist, setStatusDist] = useState<{ label: string; pct: number; tone: "primary" | "warning" | "danger" }[]>([]);
  const [conditions, setConditions] = useState<{ label: string; pct: number }[]>([]);

  // KPI rows (stored as generic arrays so backend can define them)
  const [atendKpis, setAtendKpis] = useState<{ icon: string; label: string; value: string; delta: string; deltaType: "up" | "down" }[]>([]);
  const [finKpis, setFinKpis] = useState<{ icon: string; label: string; value: string; delta: string; deltaType: "up" | "down" }[]>([]);
  const [patKpis, setPatKpis] = useState<{ icon: string; label: string; value: string; delta: string; deltaType: "up" | "down" }[]>([]);
  const [iaKpis, setIaKpis] = useState<{ icon: string; label: string; value: string; delta: string; deltaType: "up" | "down" }[]>([]);

  const fetchData = useCallback(async (p: string) => {
    try {
      setLoading(true);
      const res = await getOrgReports(p);
      const d = res.data as Record<string, unknown>;

      if (Array.isArray(d.attendance_by_month)) setAtendimentosChart(d.attendance_by_month as ChartPoint[]);
      if (Array.isArray(d.financial_by_month)) setFinanceiroChart(d.financial_by_month as ChartPoint[]);
      if (Array.isArray(d.patients_by_month)) setPacientesChart(d.patients_by_month as ChartPoint[]);
      if (Array.isArray(d.ai_by_month)) setIaChart(d.ai_by_month as ChartPoint[]);

      if (Array.isArray(d.doctor_ranking)) setDoctorRanking(d.doctor_ranking as typeof doctorRanking);
      if (Array.isArray(d.status_distribution)) setStatusDist(d.status_distribution as typeof statusDist);
      if (Array.isArray(d.conditions)) setConditions(d.conditions as typeof conditions);

      if (Array.isArray(d.attendance_kpis)) setAtendKpis(d.attendance_kpis as typeof atendKpis);
      if (Array.isArray(d.financial_kpis)) setFinKpis(d.financial_kpis as typeof finKpis);
      if (Array.isArray(d.patients_kpis)) setPatKpis(d.patients_kpis as typeof patKpis);
      if (Array.isArray(d.ai_kpis)) setIaKpis(d.ai_kpis as typeof iaKpis);
    } catch {
      // keep empty
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(period); }, [fetchData, period]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <MaterialIcon icon="hourglass_empty" size="xl" className="text-primary animate-spin" />
          <p className="text-stone-400 text-sm">Carregando relatorios...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-headline font-extrabold text-on-surface tracking-tight">
            Relatorios Gerenciais Avancados
          </h2>
          <p className="text-stone-400 text-sm mt-1 italic">
            Metricas de desempenho em tempo real
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button variant="secondary" icon="picture_as_pdf" size="sm" onClick={() => alert("Exportar PDF")}>
            Exportar PDF
          </Button>
          <Button variant="secondary" icon="download" size="sm" onClick={() => alert("Exportar CSV")}>
            Exportar CSV
          </Button>
        </div>
      </div>

      {/* Tab selector */}
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-bold font-headline transition-all",
              activeTab === tab.key
                ? "bg-primary text-on-primary-container shadow-lg shadow-primary/20"
                : "glass-panel text-stone-400 hover:text-on-surface hover:bg-white/5",
            )}
          >
            <MaterialIcon icon={tab.icon} size="sm" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Period filter */}
      <div className="flex items-center gap-2 glass-panel w-fit p-1.5 rounded-xl">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={cn(
              "px-4 py-1.5 rounded-lg text-xs font-bold transition-all",
              period === p.key
                ? "bg-primary/20 text-primary"
                : "text-stone-500 hover:text-stone-300",
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* ---------- ATENDIMENTOS ---------- */}
      {activeTab === "atendimentos" && (
        <div className="space-y-8">
          {atendKpis.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {atendKpis.map((k) => (
                <StatCard key={k.label} icon={k.icon} label={k.label} value={k.value} delta={k.delta} deltaType={k.deltaType} />
              ))}
            </div>
          )}

          {(atendimentosChart.length > 0 || doctorRanking.length > 0) && (
            <div className={cn("grid grid-cols-1 gap-6", doctorRanking.length > 0 && atendimentosChart.length > 0 && "lg:grid-cols-3")}>
              {atendimentosChart.length > 0 && (
                <Card className={cn(doctorRanking.length > 0 && "lg:col-span-2")} padding="lg">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h4 className="text-lg font-headline font-bold text-on-surface">Consultas por Periodo</h4>
                      <p className="text-xs text-stone-500">Atendimentos vs Retornos ({period})</p>
                    </div>
                    <div className="flex gap-4 text-[10px] font-bold uppercase tracking-widest">
                      <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-primary" /> Atendimentos</span>
                      <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-stone-600" /> Retornos</span>
                    </div>
                  </div>
                  <BarChart data={atendimentosChart} />
                </Card>
              )}

              {doctorRanking.length > 0 && (
                <Card padding="lg">
                  <h4 className="text-lg font-headline font-bold text-on-surface mb-4">Ranking Medicos</h4>
                  <div className="space-y-4">
                    {doctorRanking.map((doc) => (
                      <div key={doc.name} className="group">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-sm text-stone-300 font-medium">{doc.name}</span>
                          <span className="text-xs text-stone-500">{doc.count} consultas</span>
                        </div>
                        <ProgressBar value={doc.pct} size="sm" />
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {statusDist.length > 0 && (
            <Card padding="lg">
              <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Distribuicao por Status</h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                {statusDist.map((s) => (
                  <div key={s.label} className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-stone-300">{s.label}</span>
                      <Badge tone={s.tone}>{s.pct}%</Badge>
                    </div>
                    <ProgressBar value={s.pct} variant={s.tone === "primary" ? "primary" : s.tone === "warning" ? "warning" : "danger"} />
                  </div>
                ))}
              </div>
            </Card>
          )}

          {atendKpis.length === 0 && atendimentosChart.length === 0 && doctorRanking.length === 0 && statusDist.length === 0 && (
            <EmptyState period={period} />
          )}
        </div>
      )}

      {/* ---------- FINANCEIRO ---------- */}
      {activeTab === "financeiro" && (
        <div className="space-y-8">
          {finKpis.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {finKpis.map((k) => (
                <StatCard key={k.label} icon={k.icon} label={k.label} value={k.value} delta={k.delta} deltaType={k.deltaType} />
              ))}
            </div>
          )}

          {financeiroChart.length > 0 && (
            <Card padding="lg">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h4 className="text-lg font-headline font-bold text-on-surface">Receita vs Custo</h4>
                  <p className="text-xs text-stone-500">Evolucao mensal ({period})</p>
                </div>
                <div className="flex gap-4 text-[10px] font-bold uppercase tracking-widest">
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-primary" /> Receita</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-stone-600" /> Custo</span>
                </div>
              </div>
              <BarChart data={financeiroChart} />
            </Card>
          )}

          {finKpis.length === 0 && financeiroChart.length === 0 && (
            <EmptyState period={period} />
          )}
        </div>
      )}

      {/* ---------- PACIENTES ---------- */}
      {activeTab === "pacientes" && (
        <div className="space-y-8">
          {patKpis.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {patKpis.map((k) => (
                <StatCard key={k.label} icon={k.icon} label={k.label} value={k.value} delta={k.delta} deltaType={k.deltaType} />
              ))}
            </div>
          )}

          {(pacientesChart.length > 0 || conditions.length > 0) && (
            <div className={cn("grid grid-cols-1 gap-6", pacientesChart.length > 0 && conditions.length > 0 && "lg:grid-cols-3")}>
              {pacientesChart.length > 0 && (
                <Card className={cn(conditions.length > 0 && "lg:col-span-2")} padding="lg">
                  <div className="flex justify-between items-center mb-6">
                    <div>
                      <h4 className="text-lg font-headline font-bold text-on-surface">Novos Pacientes/Mes</h4>
                      <p className="text-xs text-stone-500">Evolucao de cadastros ({period})</p>
                    </div>
                  </div>
                  <BarChart data={pacientesChart} singleColor />
                </Card>
              )}

              {conditions.length > 0 && (
                <Card padding="lg">
                  <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Condicoes Clinicas</h4>
                  <div className="space-y-4">
                    {conditions.map((c) => (
                      <div key={c.label} className="group">
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-sm text-stone-300">{c.label}</span>
                          <span className="text-xs text-stone-500">{c.pct}%</span>
                        </div>
                        <ProgressBar value={c.pct} size="sm" />
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {patKpis.length === 0 && pacientesChart.length === 0 && conditions.length === 0 && (
            <EmptyState period={period} />
          )}
        </div>
      )}

      {/* ---------- IA ---------- */}
      {activeTab === "ia" && (
        <div className="space-y-8">
          {iaKpis.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {iaKpis.map((k) => (
                <StatCard key={k.label} icon={k.icon} label={k.label} value={k.value} delta={k.delta} deltaType={k.deltaType} />
              ))}
            </div>
          )}

          {iaChart.length > 0 && (
            <Card padding="lg">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h4 className="text-lg font-headline font-bold text-on-surface">Analises Realizadas</h4>
                  <p className="text-xs text-stone-500">Analises vs Custos ({period})</p>
                </div>
                <div className="flex gap-4 text-[10px] font-bold uppercase tracking-widest">
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-primary" /> Analises</span>
                  <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-stone-600" /> Custos</span>
                </div>
              </div>
              <BarChart data={iaChart} />
            </Card>
          )}

          {iaKpis.length === 0 && iaChart.length === 0 && (
            <EmptyState period={period} />
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function EmptyState({ period }: { period: string }) {
  return (
    <Card padding="lg" className="border-dashed border-outline-variant/30">
      <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
        <MaterialIcon icon="insights" size="lg" className="text-stone-600" />
        <h4 className="text-sm font-bold text-stone-400">Sem dados para o periodo selecionado</h4>
        <p className="text-xs text-stone-500 max-w-md">
          Nao ha metricas disponiveis para o periodo {period}. Tente outro intervalo
          ou aguarde novos atendimentos serem registrados.
        </p>
      </div>
    </Card>
  );
}

function BarChart({
  data,
  singleColor = false,
}: {
  data: { label: string; a: number; b: number }[];
  singleColor?: boolean;
}) {
  return (
    <div className="h-48 md:h-64 flex items-end justify-between gap-2 px-2">
      {data.map((d) => (
        <div key={d.label} className="flex flex-col items-center gap-2 w-full group">
          <div className="w-full flex items-end gap-1 h-full">
            {!singleColor && (
              <div
                className="w-full bg-stone-700/60 rounded-t-sm transition-all group-hover:bg-stone-600"
                style={{ height: `${d.b}%` }}
              />
            )}
            <div
              className="w-full bg-primary rounded-t-sm transition-all group-hover:brightness-110"
              style={{ height: `${d.a}%` }}
            />
          </div>
          <span className="text-[10px] text-stone-500 font-bold">{d.label}</span>
        </div>
      ))}
    </div>
  );
}
