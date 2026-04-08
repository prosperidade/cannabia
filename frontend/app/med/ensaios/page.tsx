"use client";

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
   Clinical Trials Panel
   TODO: replace all mock data with real API calls.
   ──────────────────────────────────────────── */

// TODO: fetch from API
const MOCK_STATS = [
  { icon: "science", label: "Ensaios Ativos", value: 8, delta: "Em andamento", deltaType: "up" as const },
  { icon: "groups", label: "Pacientes Participantes", value: "1.240", delta: "+12%", deltaType: "up" as const },
  { icon: "verified", label: "Taxa de Conclusao", value: "92%", delta: "+3.2%", deltaType: "up" as const },
  { icon: "article", label: "Publicacoes", value: 14, delta: "+2", deltaType: "up" as const },
];

// TODO: fetch from API
const MOCK_TRIALS = [
  {
    name: "Protocolo THC-G1",
    description: "Avaliacao de eficacia analgesica em dor oncologica cronica",
    phase: "Fase III",
    phaseTone: "info" as const,
    status: "Recrutando",
    statusTone: "success" as const,
    enrolled: 450,
    target: 500,
    startDate: "15/01/2025",
    endDate: "30/06/2026",
    progress: 85,
    icon: "medication",
  },
  {
    name: "Estudo Terpeno Limonene",
    description: "Correlacao entre perfil terpenico e reducao de ansiedade",
    phase: "Fase II",
    phaseTone: "warning" as const,
    status: "Em Andamento",
    statusTone: "primary" as const,
    enrolled: 120,
    target: 150,
    startDate: "01/03/2025",
    endDate: "15/09/2026",
    progress: 62,
    icon: "biotech",
  },
  {
    name: "C-Beta-Myrcene 204",
    description: "Estudo de biodisponibilidade de formulacao nano-emulsificada",
    phase: "Fase I",
    phaseTone: "success" as const,
    status: "Completo",
    statusTone: "neutral" as const,
    enrolled: 45,
    target: 50,
    startDate: "10/06/2024",
    endDate: "20/12/2025",
    progress: 90,
    icon: "science",
  },
  {
    name: "Nano-Emulsion CBD",
    description: "Comparacao de biodisponibilidade sublingual vs oral de CBD nano-emulsificado",
    phase: "Fase III",
    phaseTone: "info" as const,
    status: "Recrutando",
    statusTone: "success" as const,
    enrolled: 310,
    target: 400,
    startDate: "01/08/2025",
    endDate: "28/02/2027",
    progress: 77,
    icon: "pill",
  },
];

// TODO: fetch from API
const MOCK_FINDINGS = [
  {
    trial: "Protocolo THC-G1",
    finding: "Reducao de 34% na escala VAS de dor no grupo tratamento vs placebo (p < 0.001).",
    type: "Eficacia",
    typeTone: "success" as const,
  },
  {
    trial: "Estudo Terpeno Limonene",
    finding: "Limonene em concentracao 0.5% demonstrou reducao de 22% nos scores de ansiedade (GAD-7).",
    type: "Correlacao",
    typeTone: "primary" as const,
  },
  {
    trial: "C-Beta-Myrcene 204",
    finding: "Formulacao nano apresentou biodisponibilidade 3.2x superior a formulacao convencional.",
    type: "Farmacocinetica",
    typeTone: "info" as const,
  },
];

// TODO: fetch from API
const MOCK_ELIGIBILITY = [
  { criteria: "Idade entre 18 e 75 anos", met: true },
  { criteria: "Diagnostico confirmado de dor cronica (> 6 meses)", met: true },
  { criteria: "Sem uso de opioides nos ultimos 30 dias", met: true },
  { criteria: "Funcao hepatica dentro da normalidade (ALT/AST)", met: false },
  { criteria: "Consentimento informado assinado", met: true },
];

// TODO: fetch from API
const MOCK_RECRUITMENT = [
  { label: "Jan", value: 40 },
  { label: "Fev", value: 60 },
  { label: "Mar", value: 55 },
  { label: "Abr", value: 85 },
  { label: "Mai", value: 95 },
];

const maxRecruitValue = Math.max(...MOCK_RECRUITMENT.map((d) => d.value));

export default function EnsaiosPage() {
  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Painel de Ensaios Clinicos
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            Monitoramento em tempo real de protocolos de pesquisa Cannab&apos;IA.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm">
            <MaterialIcon icon="file_download" size="sm" />
            <span className="hidden sm:inline ml-1">Exportar</span>
          </Button>
          <Button size="sm">
            <MaterialIcon icon="add" size="sm" />
            <span className="ml-1">Novo Ensaio</span>
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

      {/* ── Trials Table + Recruitment Chart ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trials List */}
        <div className="lg:col-span-2">
          <Card variant="glass" padding="sm" className="rounded-3xl overflow-hidden">
            <div className="p-4 md:p-6 border-b border-white/5 flex justify-between items-center">
              <h3 className="font-bold text-on-surface font-headline text-lg">
                Protocolos em Andamento
              </h3>
              <Badge tone="primary">{MOCK_TRIALS.length} ativos</Badge>
            </div>

            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-white/5">
                  <tr>
                    <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                      Nome do Protocolo
                    </th>
                    <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                      Fase
                    </th>
                    <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                      Participantes
                    </th>
                    <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                      Progresso
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {MOCK_TRIALS.map((trial) => (
                    <tr
                      key={trial.name}
                      className="hover:bg-white/5 transition-colors cursor-pointer"
                    >
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center">
                            <MaterialIcon icon={trial.icon} size="sm" className="text-primary" />
                          </div>
                          <div>
                            <span className="text-sm font-semibold text-on-surface">
                              {trial.name}
                            </span>
                            <p className="text-[10px] text-stone-500 mt-0.5">
                              {trial.description}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <Badge tone={trial.phaseTone}>{trial.phase}</Badge>
                      </td>
                      <td className="px-6 py-5 text-sm text-stone-300">
                        {trial.enrolled}/{trial.target}
                      </td>
                      <td className="px-6 py-5 w-40">
                        <ProgressBar value={trial.progress} variant="primary" size="sm" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden p-4 space-y-4">
              {MOCK_TRIALS.map((trial) => (
                <div
                  key={trial.name}
                  className="p-4 rounded-xl bg-surface-container/50 border border-white/5 border-l-4 border-l-primary space-y-3"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-bold text-on-surface text-sm">{trial.name}</h4>
                      <p className="text-xs text-stone-500 mt-0.5">{trial.description}</p>
                    </div>
                    <Badge tone={trial.phaseTone}>{trial.phase}</Badge>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] uppercase tracking-widest text-stone-500">
                      <span>Progresso</span>
                      <span>{trial.progress}%</span>
                    </div>
                    <ProgressBar value={trial.progress} variant="primary" size="sm" />
                  </div>
                  <div className="flex items-center gap-1 text-xs text-stone-400">
                    <MaterialIcon icon="groups" size="sm" className="text-primary" />
                    <span>{trial.enrolled} Pacientes</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Recruitment Chart */}
        <Card variant="glass" padding="lg" className="rounded-3xl flex flex-col">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h3 className="font-bold text-on-surface font-headline text-lg">
                Taxa de Sucesso
              </h3>
              <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                Recrutamento Mensal
              </p>
            </div>
            <MaterialIcon icon="bar_chart" className="text-stone-500" />
          </div>
          <div className="flex-1 flex items-end justify-between gap-2 h-48 mb-6 px-2">
            {MOCK_RECRUITMENT.map((d, i) => {
              const heightPct = (d.value / maxRecruitValue) * 100;
              const isMax = d.value === maxRecruitValue;
              return (
                <div key={d.label} className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                  <div
                    className={cn(
                      "w-full rounded-t-lg transition-all",
                      isMax
                        ? "bg-primary shadow-[0_0_20px_rgba(163,201,58,0.3)]"
                        : "bg-primary/20 hover:bg-primary/40",
                    )}
                    style={{ height: `${heightPct}%` }}
                  />
                  <span
                    className={cn(
                      "text-[10px] font-bold",
                      isMax ? "text-primary" : "text-stone-500",
                    )}
                  >
                    {d.label}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="bg-white/5 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-stone-400">Meta Trimestral</span>
              <span className="text-xs font-bold text-primary">82%</span>
            </div>
            <ProgressBar value={82} variant="primary" size="sm" />
          </div>
        </Card>
      </div>

      {/* ── Findings + Eligibility ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Resultados Preliminares */}
        <Card variant="glass" padding="lg" className="rounded-3xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon icon="labs" className="text-primary" size="lg" />
            <div>
              <h3 className="text-lg font-bold text-on-surface font-headline">
                Resultados Preliminares
              </h3>
              <p className="text-xs text-stone-500">Descobertas-chave dos ensaios em curso</p>
            </div>
          </div>
          <div className="space-y-4">
            {MOCK_FINDINGS.map((f, i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-surface-container/50 border border-white/5 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-primary">{f.trial}</span>
                  <Badge tone={f.typeTone}>{f.type}</Badge>
                </div>
                <p className="text-sm text-stone-300 leading-relaxed">{f.finding}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* Criterios de Elegibilidade */}
        <Card variant="glass" padding="lg" className="rounded-3xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon icon="checklist" className="text-primary" size="lg" />
            <div>
              <h3 className="text-lg font-bold text-on-surface font-headline">
                Criterios de Elegibilidade
              </h3>
              <p className="text-xs text-stone-500">
                Verificacao para Protocolo THC-G1
              </p>
            </div>
          </div>
          <div className="space-y-3">
            {MOCK_ELIGIBILITY.map((e, i) => (
              <div
                key={i}
                className={cn(
                  "flex items-center gap-4 p-4 rounded-xl border transition-all",
                  e.met
                    ? "bg-emerald-500/5 border-emerald-500/20"
                    : "bg-error/5 border-error/20",
                )}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                    e.met ? "bg-emerald-500/20" : "bg-error/20",
                  )}
                >
                  <MaterialIcon
                    icon={e.met ? "check" : "close"}
                    size="sm"
                    className={e.met ? "text-emerald-400" : "text-error"}
                  />
                </div>
                <span className={cn("text-sm", e.met ? "text-stone-300" : "text-stone-400")}>
                  {e.criteria}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-white/5 flex justify-between items-center">
            <span className="text-xs text-stone-500">
              {MOCK_ELIGIBILITY.filter((e) => e.met).length}/{MOCK_ELIGIBILITY.length} criterios atendidos
            </span>
            <Badge
              tone={
                MOCK_ELIGIBILITY.every((e) => e.met) ? "success" : "warning"
              }
            >
              {MOCK_ELIGIBILITY.every((e) => e.met) ? "ELEGIVEL" : "PARCIAL"}
            </Badge>
          </div>
        </Card>
      </div>

      {/* ── AI Insights ── */}
      <Card variant="glass" padding="lg" className="rounded-3xl border-l-4 border-primary relative overflow-hidden">
        <div className="absolute -right-8 -top-8 w-32 h-32 bg-primary/10 rounded-full blur-2xl pointer-events-none" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-4">
            <MaterialIcon
              icon="auto_awesome"
              className="text-amber-500"
            />
            <span className="text-[10px] font-bold text-amber-500 uppercase tracking-widest">
              Previsoes da IA
            </span>
          </div>
          <p className="text-sm text-stone-300 leading-relaxed italic mb-6">
            &quot;Com base nos dados atuais de adesao e recrutamento do Protocolo THC-G1, prevemos uma
            conclusao 14 dias antes do cronograma original, com eficacia projetada 8.2% acima da
            media do setor.&quot;
          </p>
          <div className="flex flex-wrap gap-3">
            <Button variant="secondary" size="sm">
              Analisar Riscos
            </Button>
            <Button variant="secondary" size="sm">
              Otimizar Dosagem
            </Button>
          </div>
        </div>
      </Card>
    </section>
  );
}
