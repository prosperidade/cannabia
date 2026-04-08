"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import {
  Card,
  Badge,
  Button,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ────────────────────────────────────────────
   Botanical Precision - Strain/Cultivar Analysis
   TODO: replace all mock data with real API calls.
   ──────────────────────────────────────────── */

// TODO: fetch from API
const MOCK_CULTIVAR = {
  name: "Aura-7 Hybrid",
  type: "Hibrido dominante Sativa",
  origin: "Cultivo Controlado Indoor - Lote #BT-4421",
  thc: 24.2,
  cbd: 2.1,
  cbg: 1.8,
  cbn: 0.4,
};

// TODO: fetch from API
const MOCK_TERPENES = [
  { name: "Myrcene", pct: 0.8, color: "bg-primary", effect: "Sedativo, Analgesico" },
  { name: "Limonene", pct: 0.5, color: "bg-amber-500", effect: "Ansiolítico, Melhora do humor" },
  { name: "Linalool", pct: 0.3, color: "bg-purple-400", effect: "Relaxante, Anti-convulsivo" },
  { name: "Caryophyllene", pct: 0.25, color: "bg-orange-400", effect: "Anti-inflamatorio, Analgesico" },
  { name: "Pinene", pct: 0.15, color: "bg-emerald-400", effect: "Broncodilatador, Estimulante" },
  { name: "Humulene", pct: 0.1, color: "bg-blue-400", effect: "Anti-inflamatorio, Redutor de apetite" },
];

const maxTerpenePct = Math.max(...MOCK_TERPENES.map((t) => t.pct));

// TODO: fetch from API
const MOCK_COMPATIBILITY = {
  score: 91,
  patient: "Elena Sterling",
  condition: "Neuralgia Cronica",
  factors: [
    { label: "Perfil cannabinoide", score: 95, status: "Otimo" },
    { label: "Perfil terpenico", score: 88, status: "Bom" },
    { label: "Historico de resposta", score: 92, status: "Otimo" },
    { label: "Interacoes medicamentosas", score: 85, status: "Aceitavel" },
  ],
};

// TODO: fetch from API
const MOCK_EFFECTS = [
  { icon: "self_improvement", label: "Relaxamento", pct: 85, desc: "Efeito primario dominante" },
  { icon: "health_and_safety", label: "Analgesia", pct: 78, desc: "Reducao significativa da percepcao de dor" },
  { icon: "healing", label: "Anti-inflamatorio", pct: 72, desc: "Modulacao de citocinas pro-inflamatorias" },
  { icon: "bedtime", label: "Inducao de Sono", pct: 65, desc: "Melhora do tempo para adormecer e qualidade do sono" },
  { icon: "psychology", label: "Ansiolise", pct: 60, desc: "Reducao de sintomas ansiosos (GAD-7)" },
  { icon: "restaurant", label: "Apetite", pct: 45, desc: "Estimulacao moderada do apetite" },
];

// TODO: fetch from API
const MOCK_RECOMMENDATIONS = [
  {
    name: "Blue Dream",
    type: "Hibrido Sativa",
    match: 94,
    thc: 21.0,
    cbd: 2.3,
    terpene: "Myrcene + Limonene",
    reason: "Perfil terpenico complementar com boa eficacia analgesica",
  },
  {
    name: "ACDC",
    type: "Dominante CBD",
    match: 89,
    thc: 1.2,
    cbd: 20.1,
    terpene: "Myrcene + Caryophyllene",
    reason: "Alternativa de baixo THC para sessoes diurnas",
  },
  {
    name: "Harlequin",
    type: "Sativa",
    match: 86,
    thc: 5.0,
    cbd: 12.0,
    terpene: "Myrcene + Pinene",
    reason: "Equilibrio CBD:THC para manutenção funcional",
  },
  {
    name: "Cannatonic",
    type: "Hibrido",
    match: 82,
    thc: 3.5,
    cbd: 15.0,
    terpene: "Linalool + Myrcene",
    reason: "Indicado para protocolo noturno com inducao de sono",
  },
];

export default function BotanicalPage() {
  const [selectedStrain, setSelectedStrain] = useState<string | null>(null);

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Precisao Botanica
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            Analise de Precisao Botanica - Perfil de cultivar e compatibilidade terapeutica
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm">
            <MaterialIcon icon="compare" size="sm" />
            <span className="hidden sm:inline ml-1">Comparar</span>
          </Button>
          <Button size="sm">
            <MaterialIcon icon="download" size="sm" />
            <span className="ml-1">Exportar</span>
          </Button>
        </div>
      </div>

      {/* ── Cultivar Analysis + Compatibility ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Strain Card */}
        <div className="lg:col-span-8">
          <Card variant="glass" padding="lg" className="rounded-3xl relative overflow-hidden">
            <div className="absolute -bottom-10 -right-10 opacity-5 pointer-events-none">
              <span
                className="material-symbols-outlined text-[180px]"
                style={{ fontVariationSettings: "'wght' 100" }}
              >
                eco
              </span>
            </div>
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-stone-500">
                    Perfil de Cultivar
                  </p>
                  <h3 className="text-2xl font-black text-primary font-headline">
                    {MOCK_CULTIVAR.name}
                  </h3>
                  <p className="text-xs text-stone-500 mt-1">{MOCK_CULTIVAR.origin}</p>
                </div>
                <Badge tone="primary">{MOCK_CULTIVAR.type}</Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Cannabinoid ratios */}
                <div className="space-y-4">
                  <span className="text-[10px] uppercase tracking-widest text-stone-500">
                    Proporcao de Canabinoides
                  </span>
                  <div className="space-y-3">
                    {[
                      { name: "THC", value: MOCK_CULTIVAR.thc, pct: 84 },
                      { name: "CBD", value: MOCK_CULTIVAR.cbd, pct: 15 },
                      { name: "CBG", value: MOCK_CULTIVAR.cbg, pct: 12 },
                      { name: "CBN", value: MOCK_CULTIVAR.cbn, pct: 5 },
                    ].map((c) => (
                      <div key={c.name} className="space-y-1">
                        <div className="flex justify-between text-xs font-semibold">
                          <span className="text-stone-300">{c.name}</span>
                          <span className="text-primary">{c.value}%</span>
                        </div>
                        <ProgressBar value={c.pct} variant="primary" glow size="md" />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Terpene Map */}
                <div className="space-y-4">
                  <span className="text-[10px] uppercase tracking-widest text-stone-500">
                    Mapa de Terpenos
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {MOCK_TERPENES.map((t) => (
                      <div
                        key={t.name}
                        className="px-3 py-2 rounded-xl bg-white/5 border border-white/5 flex items-center gap-2 hover:border-primary/20 transition-all cursor-default"
                      >
                        <div
                          className={cn("w-3 h-3 rounded-full", t.color)}
                        />
                        <span className="text-xs font-bold text-on-surface">{t.name}</span>
                        <span className="text-[10px] text-primary font-bold">{t.pct}%</span>
                      </div>
                    ))}
                  </div>

                  {/* Terpene bars */}
                  <div className="space-y-3 mt-4">
                    {MOCK_TERPENES.map((t) => (
                      <div key={`bar-${t.name}`} className="space-y-1">
                        <div className="flex justify-between text-[10px]">
                          <span className="text-stone-400">{t.name}</span>
                          <span className="text-stone-300">{t.effect}</span>
                        </div>
                        <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
                          <div
                            className={cn("h-full rounded-full transition-all", t.color)}
                            style={{ width: `${(t.pct / maxTerpenePct) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Compatibility Score */}
        <div className="lg:col-span-4 space-y-6">
          <Card
            variant="glass"
            padding="lg"
            className="rounded-3xl border-2 border-primary/20 flex flex-col items-center justify-center text-center"
          >
            <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-4">
              Compatibilidade com Paciente
            </p>
            <div className="relative flex items-center justify-center mb-4">
              <svg className="w-36 h-36 -rotate-90">
                <circle
                  className="text-surface-container-highest"
                  cx="72"
                  cy="72"
                  r="64"
                  fill="transparent"
                  stroke="currentColor"
                  strokeWidth="8"
                />
                <circle
                  className="text-primary"
                  cx="72"
                  cy="72"
                  r="64"
                  fill="transparent"
                  stroke="currentColor"
                  strokeDasharray={2 * Math.PI * 64}
                  strokeDashoffset={
                    2 * Math.PI * 64 * (1 - MOCK_COMPATIBILITY.score / 100)
                  }
                  strokeLinecap="round"
                  strokeWidth="8"
                  style={{
                    filter: "drop-shadow(0 0 12px rgba(190,230,84,0.6))",
                  }}
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-4xl font-black text-on-surface tracking-tighter">
                  {MOCK_COMPATIBILITY.score}%
                </span>
                <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                  Compatibilidade
                </span>
              </div>
            </div>
            <p className="text-sm font-semibold text-stone-200">
              {MOCK_COMPATIBILITY.patient}
            </p>
            <p className="text-xs text-stone-500 mt-1">{MOCK_COMPATIBILITY.condition}</p>
          </Card>

          {/* Compatibility Factors */}
          <Card variant="glass" padding="md" className="rounded-3xl">
            <h4 className="text-sm font-bold text-stone-400 uppercase tracking-widest mb-4">
              Fatores de Compatibilidade
            </h4>
            <div className="space-y-3">
              {MOCK_COMPATIBILITY.factors.map((f) => (
                <div key={f.label} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-stone-400">{f.label}</span>
                    <span className="font-bold text-on-surface">{f.score}%</span>
                  </div>
                  <ProgressBar
                    value={f.score}
                    variant={f.score >= 90 ? "success" : f.score >= 80 ? "primary" : "warning"}
                    size="sm"
                  />
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* ── Expected Effects ── */}
      <Card variant="glass" padding="lg" className="rounded-3xl">
        <div className="flex items-center gap-3 mb-6">
          <MaterialIcon icon="vital_signs" className="text-primary" size="lg" />
          <div>
            <h3 className="text-lg font-bold text-on-surface font-headline">
              Efeitos Esperados
            </h3>
            <p className="text-xs text-stone-500">
              Previsao terapeutica baseada no perfil molecular
            </p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {MOCK_EFFECTS.map((e) => (
            <div
              key={e.label}
              className="p-4 rounded-xl bg-surface-container/50 border border-white/5 hover:border-primary/20 transition-all space-y-3"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <MaterialIcon icon={e.icon} className="text-primary" />
                </div>
                <div className="flex-1 min-w-0">
                  <h5 className="text-sm font-bold text-on-surface">{e.label}</h5>
                  <p className="text-[10px] text-stone-500 truncate">{e.desc}</p>
                </div>
                <span className="text-sm font-black text-primary">{e.pct}%</span>
              </div>
              <ProgressBar
                value={e.pct}
                variant={e.pct >= 70 ? "primary" : e.pct >= 50 ? "warning" : "danger"}
                size="sm"
              />
            </div>
          ))}
        </div>
      </Card>

      {/* ── Strain Recommendations ── */}
      <Card variant="glass" padding="lg" className="rounded-3xl">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <MaterialIcon icon="recommend" className="text-primary" size="lg" />
            <div>
              <h3 className="text-lg font-bold text-on-surface font-headline">
                Cepas Recomendadas
              </h3>
              <p className="text-xs text-stone-500">
                Sugestoes baseadas no perfil do paciente
              </p>
            </div>
          </div>
          <Badge tone="primary">{MOCK_RECOMMENDATIONS.length} sugestoes</Badge>
        </div>

        {/* Desktop table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-white/5">
              <tr>
                <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                  Cepa
                </th>
                <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                  Tipo
                </th>
                <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                  THC/CBD
                </th>
                <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                  Terpenos
                </th>
                <th className="px-6 py-4 text-[10px] font-bold uppercase tracking-widest text-stone-500 text-right">
                  Compatibilidade
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {MOCK_RECOMMENDATIONS.map((r) => (
                <tr
                  key={r.name}
                  className={cn(
                    "hover:bg-white/5 transition-colors cursor-pointer",
                    selectedStrain === r.name && "bg-primary/5",
                  )}
                  onClick={() =>
                    setSelectedStrain(selectedStrain === r.name ? null : r.name)
                  }
                >
                  <td className="px-6 py-4">
                    <div>
                      <span className="text-sm font-semibold text-on-surface">{r.name}</span>
                      {selectedStrain === r.name && (
                        <p className="text-[10px] text-stone-500 mt-1 italic">{r.reason}</p>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <Badge tone="neutral">{r.type}</Badge>
                  </td>
                  <td className="px-6 py-4 text-sm text-stone-300">
                    {r.thc}% / {r.cbd}%
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-xs text-stone-400 bg-surface-container px-2 py-1 rounded-full">
                      {r.terpene}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span
                      className={cn(
                        "text-lg font-black",
                        r.match >= 90
                          ? "text-primary"
                          : r.match >= 80
                            ? "text-amber-400"
                            : "text-stone-400",
                      )}
                    >
                      {r.match}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile cards */}
        <div className="md:hidden space-y-3">
          {MOCK_RECOMMENDATIONS.map((r) => (
            <div
              key={r.name}
              className="p-4 rounded-xl bg-surface-container/50 border border-white/5 hover:border-primary/20 transition-all cursor-pointer"
              onClick={() =>
                setSelectedStrain(selectedStrain === r.name ? null : r.name)
              }
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h5 className="text-sm font-bold text-on-surface">{r.name}</h5>
                  <p className="text-[10px] text-stone-500">{r.type}</p>
                </div>
                <span
                  className={cn(
                    "text-xl font-black",
                    r.match >= 90 ? "text-primary" : "text-amber-400",
                  )}
                >
                  {r.match}%
                </span>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px]">
                <span className="text-stone-400 bg-surface-container px-2 py-0.5 rounded-full">
                  THC {r.thc}%
                </span>
                <span className="text-stone-400 bg-surface-container px-2 py-0.5 rounded-full">
                  CBD {r.cbd}%
                </span>
                <span className="text-stone-400 bg-surface-container px-2 py-0.5 rounded-full">
                  {r.terpene}
                </span>
              </div>
              {selectedStrain === r.name && (
                <p className="text-xs text-stone-400 mt-2 italic">{r.reason}</p>
              )}
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}
