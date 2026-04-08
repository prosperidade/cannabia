"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import {
  Card,
  StatCard,
  Button,
  Badge,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ------------------------------------------------------------------ */
/*  Mock data                                                          */
/* ------------------------------------------------------------------ */

type TabKey = "atendimentos" | "financeiro" | "pacientes" | "ia";
type PeriodKey = "7d" | "30d" | "90d" | "12m";

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

const ATENDIMENTOS_CHART = [
  { label: "Jan", a: 62, b: 44 },
  { label: "Fev", a: 78, b: 50 },
  { label: "Mar", a: 85, b: 60 },
  { label: "Abr", a: 90, b: 55 },
  { label: "Mai", a: 100, b: 70 },
  { label: "Jun", a: 88, b: 65 },
  { label: "Jul", a: 95, b: 72 },
];

const FINANCEIRO_CHART = [
  { label: "Jan", a: 45, b: 30 },
  { label: "Fev", a: 55, b: 35 },
  { label: "Mar", a: 60, b: 32 },
  { label: "Abr", a: 70, b: 40 },
  { label: "Mai", a: 85, b: 45 },
  { label: "Jun", a: 78, b: 42 },
  { label: "Jul", a: 92, b: 48 },
];

const PACIENTES_CHART = [
  { label: "Jan", a: 40, b: 0 },
  { label: "Fev", a: 52, b: 0 },
  { label: "Mar", a: 58, b: 0 },
  { label: "Abr", a: 65, b: 0 },
  { label: "Mai", a: 80, b: 0 },
  { label: "Jun", a: 75, b: 0 },
  { label: "Jul", a: 90, b: 0 },
];

const IA_CHART = [
  { label: "Jan", a: 30, b: 20 },
  { label: "Fev", a: 50, b: 28 },
  { label: "Mar", a: 65, b: 35 },
  { label: "Abr", a: 72, b: 42 },
  { label: "Mai", a: 88, b: 50 },
  { label: "Jun", a: 95, b: 55 },
  { label: "Jul", a: 100, b: 60 },
];

const DOCTOR_RANKING = [
  { name: "Dra. Maria Santos", count: 142, pct: 100 },
  { name: "Dr. Joao Oliveira", count: 118, pct: 83 },
  { name: "Dra. Ana Costa", count: 96, pct: 68 },
  { name: "Dr. Pedro Lima", count: 74, pct: 52 },
];

const STATUS_DIST = [
  { label: "Concluidas", pct: 72, tone: "primary" as const },
  { label: "Em andamento", pct: 18, tone: "warning" as const },
  { label: "Canceladas", pct: 10, tone: "danger" as const },
];

const CONDITIONS = [
  { label: "Dor Cronica", pct: 38 },
  { label: "Ansiedade", pct: 28 },
  { label: "Epilepsia", pct: 18 },
  { label: "Insonia", pct: 12 },
  { label: "Outros", pct: 4 },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function RelatoriosPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("atendimentos");
  const [period, setPeriod] = useState<PeriodKey>("30d");

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
          <Button variant="secondary" icon="picture_as_pdf" size="sm" onClick={() => alert("Exportar PDF (mock)")}>
            Exportar PDF
          </Button>
          <Button variant="secondary" icon="download" size="sm" onClick={() => alert("Exportar CSV (mock)")}>
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
          {/* KPI row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard icon="event_note" label="Total Consultas" value="1.248" delta="+12%" deltaType="up" />
            <StatCard icon="avg_pace" label="Media/dia" value="18.4" delta="+3.2" deltaType="up" />
            <StatCard icon="timer" label="Tempo Medio" value="32 min" delta="-5 min" deltaType="up" />
            <StatCard icon="task_alt" label="Taxa Conclusao" value="92%" delta="+2%" deltaType="up" />
          </div>

          {/* Chart + insights */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2" padding="lg">
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
              <BarChart data={ATENDIMENTOS_CHART} />
            </Card>

            <Card padding="lg">
              <h4 className="text-lg font-headline font-bold text-on-surface mb-4">Ranking Medicos</h4>
              <div className="space-y-4">
                {DOCTOR_RANKING.map((doc) => (
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
          </div>

          {/* Status distribution */}
          <Card padding="lg">
            <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Distribuicao por Status</h4>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {STATUS_DIST.map((s) => (
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
        </div>
      )}

      {/* ---------- FINANCEIRO ---------- */}
      {activeTab === "financeiro" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard icon="payments" label="Receita Total" value="R$ 248.500" delta="+18%" deltaType="up" />
            <StatCard icon="account_balance" label="Custos" value="R$ 86.200" delta="+4%" deltaType="down" />
            <StatCard icon="trending_up" label="Margem Liquida" value="65.3%" delta="+2.1%" deltaType="up" />
            <StatCard icon="receipt_long" label="Ticket Medio" value="R$ 320" delta="+8%" deltaType="up" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2" padding="lg">
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
              <BarChart data={FINANCEIRO_CHART} />
            </Card>

            <Card padding="lg">
              <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Composicao de Custos</h4>
              <div className="space-y-4">
                {[
                  { label: "Pessoal", pct: 45 },
                  { label: "Insumos", pct: 25 },
                  { label: "Tecnologia", pct: 15 },
                  { label: "Administrativo", pct: 10 },
                  { label: "Outros", pct: 5 },
                ].map((item) => (
                  <div key={item.label} className="group">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm text-stone-300">{item.label}</span>
                      <span className="text-xs text-stone-500">{item.pct}%</span>
                    </div>
                    <ProgressBar value={item.pct} size="sm" />
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* Summary insight cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            {[
              { icon: "savings", title: "Economia Projetada", value: "R$ 12.400/mes", desc: "Otimizacao de processos com IA" },
              { icon: "trending_up", title: "Crescimento MoM", value: "+14.2%", desc: "Comparado ao mes anterior" },
              { icon: "account_balance_wallet", title: "Previsao Trimestral", value: "R$ 780.000", desc: "Baseado na tendencia atual" },
            ].map((card) => (
              <Card key={card.title} padding="md" className="flex items-start gap-4">
                <div className="p-3 bg-primary/10 rounded-xl shrink-0">
                  <MaterialIcon icon={card.icon} className="text-primary" />
                </div>
                <div>
                  <p className="text-xs text-stone-500 uppercase tracking-widest font-bold">{card.title}</p>
                  <p className="text-xl font-headline font-extrabold text-on-surface mt-1">{card.value}</p>
                  <p className="text-xs text-stone-500 mt-1">{card.desc}</p>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* ---------- PACIENTES ---------- */}
      {activeTab === "pacientes" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard icon="person_add" label="Novos/Mes" value="86" delta="+22%" deltaType="up" />
            <StatCard icon="group" label="Ativos Total" value="1.450" delta="+4.2%" deltaType="up" />
            <StatCard icon="sync" label="Taxa Retencao" value="92.4%" delta="+1.8%" deltaType="up" />
            <StatCard icon="diversity_3" label="NPS" value="78" delta="+5" deltaType="up" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2" padding="lg">
              <div className="flex justify-between items-center mb-6">
                <div>
                  <h4 className="text-lg font-headline font-bold text-on-surface">Novos Pacientes/Mes</h4>
                  <p className="text-xs text-stone-500">Evolucao de cadastros ({period})</p>
                </div>
              </div>
              <BarChart data={PACIENTES_CHART} singleColor />
            </Card>

            <Card padding="lg">
              <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Condicoes Clinicas</h4>
              <div className="space-y-4">
                {CONDITIONS.map((c) => (
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
          </div>

          {/* Retention insight */}
          <Card padding="lg" className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-secondary/10 rounded-2xl">
                <MaterialIcon icon="trending_up" className="text-secondary" size="lg" />
              </div>
              <div>
                <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">Taxa de Retencao</p>
                <h5 className="text-2xl font-headline font-extrabold text-on-surface">92.4%</h5>
                <p className="text-xs text-stone-500 mt-1">Pacientes que retornam em ate 90 dias</p>
              </div>
            </div>
            <div className="flex gap-8">
              {[
                { label: "Retorno medio", value: "42 dias" },
                { label: "Satisfacao", value: "4.7/5.0" },
                { label: "Indicacoes", value: "234" },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold mb-1">{s.label}</p>
                  <p className="text-lg font-headline font-extrabold text-on-surface">{s.value}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ---------- IA ---------- */}
      {activeTab === "ia" && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <StatCard icon="auto_awesome" label="Analises Realizadas" value="3.842" delta="+28%" deltaType="up" />
            <StatCard icon="verified" label="Precisao" value="96.2%" delta="+1.4%" deltaType="up" />
            <StatCard icon="paid" label="Custo Total" value="US$ 124.80" delta="-12%" deltaType="up" />
            <StatCard icon="speed" label="Tempo de Resposta" value="2.4s" delta="-0.8s" deltaType="up" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2" padding="lg">
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
              <BarChart data={IA_CHART} />
            </Card>

            <Card padding="lg">
              <h4 className="text-lg font-headline font-bold text-on-surface mb-6">Uso por Modelo de Analise</h4>
              <div className="space-y-4">
                {[
                  { label: "GPT-4", pct: 55, tokens: "2.1M creditos" },
                  { label: "Gemini Pro", pct: 30, tokens: "1.2M creditos" },
                  { label: "GPT-3.5", pct: 10, tokens: "380K creditos" },
                  { label: "Busca Cientifica", pct: 5, tokens: "150K creditos" },
                ].map((m) => (
                  <div key={m.label} className="group">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm text-stone-300">{m.label}</span>
                      <span className="text-xs text-stone-500">{m.tokens}</span>
                    </div>
                    <ProgressBar value={m.pct} size="sm" />
                  </div>
                ))}
              </div>
            </Card>
          </div>

          {/* AI strategic forecast card */}
          <Card padding="lg" className="bg-gradient-to-br from-primary/10 to-transparent border-primary/20 relative overflow-hidden">
            <div className="absolute -top-4 -right-4 w-24 h-24 bg-primary/10 blur-3xl" />
            <div className="flex items-center gap-2 text-primary mb-4">
              <MaterialIcon icon="auto_awesome" size="sm" filled />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">Previsao Estrategica</span>
            </div>
            <h4 className="text-xl font-headline font-bold text-on-surface leading-tight mb-4">
              Otimizacao do Fluxo Clinico
            </h4>
            <p className="text-stone-300 text-sm leading-relaxed">
              Com base na tendencia atual, recomendamos aumentar a{" "}
              <span className="text-primary font-bold">capacidade de analise em 15%</span>{" "}
              para o proximo trimestre. O modelo GPT-4 apresenta melhor custo-beneficio para anamneses complexas.
            </p>
            <div className="mt-6">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">Score de Confianca</span>
                <span className="text-xs font-bold text-primary">98%</span>
              </div>
              <ProgressBar value={98} glow />
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

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
