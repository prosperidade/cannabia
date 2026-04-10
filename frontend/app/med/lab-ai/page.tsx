"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/cn";
import { getLabAnalysis } from "@/lib/api";
import {
  Card,
  Badge,
  Button,
  MaterialIcon,
  ProgressBar,
} from "@/components/ui-tw";

/* ────────────────────────────────────────────
   AI Lab Analysis Report
   ──────────────────────────────────────────── */

type Patient = { name: string; id: string; condition: string; protocol: string; batchId: string };
type Cannabinoid = { name: string; value: number; pct: number; color: "primary" };
type Terpene = { name: string; value: string; pct: number };
type Interaction = { drug: string; severity: "danger" | "warning" | "info" | "neutral"; description: string; mechanism: string };
type Formulation = Record<string, string>;
type Reference = { title: string; source: string; doi: string };
type EffectItem = { icon: string; label: string; desc: string };

const FALLBACK_PATIENT: Patient = { name: "—", id: "—", condition: "—", protocol: "—", batchId: "—" };
const FALLBACK_CANNABINOIDS: Cannabinoid[] = [];
const FALLBACK_TERPENES: Terpene[] = [];
const FALLBACK_INTERACTIONS: Interaction[] = [];
const FALLBACK_FORMULATION: Formulation = {};
const FALLBACK_REFERENCES: Reference[] = [];
const FALLBACK_CONFIDENCE = 0;
const FALLBACK_EFFECTS: EffectItem[] = [];

export default function LabAiPage() {
  const [loading, setLoading] = useState(true);
  const [patient, setPatient] = useState<Patient>(FALLBACK_PATIENT);
  const [cannabinoids, setCannabinoids] = useState<Cannabinoid[]>(FALLBACK_CANNABINOIDS);
  const [terpenes, setTerpenes] = useState<Terpene[]>(FALLBACK_TERPENES);
  const [interactions, setInteractions] = useState<Interaction[]>(FALLBACK_INTERACTIONS);
  const [formulation, setFormulation] = useState<Formulation>(FALLBACK_FORMULATION);
  const [references, setReferences] = useState<Reference[]>(FALLBACK_REFERENCES);
  const [confidence, setConfidence] = useState(FALLBACK_CONFIDENCE);
  const [effects, setEffects] = useState<EffectItem[]>(FALLBACK_EFFECTS);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getLabAnalysis();
      const d = res.data as Record<string, unknown>;

      if (d.patient) setPatient(d.patient as Patient);
      if (Array.isArray(d.cannabinoids)) setCannabinoids(d.cannabinoids as Cannabinoid[]);
      if (Array.isArray(d.terpenes)) setTerpenes(d.terpenes as Terpene[]);
      if (Array.isArray(d.interactions)) setInteractions(d.interactions as Interaction[]);
      if (d.formulation) setFormulation(d.formulation as Formulation);
      if (Array.isArray(d.references)) setReferences(d.references as Reference[]);
      if (typeof d.confidence === "number") setConfidence(d.confidence);
      if (Array.isArray(d.effects)) setEffects(d.effects as EffectItem[]);
    } catch {
      // keep fallback data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) {
    return (
      <section className="p-4 md:p-8 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <MaterialIcon icon="hourglass_empty" size="xl" className="text-primary animate-spin" />
          <p className="text-stone-400 text-sm">Carregando analise laboratorial...</p>
        </div>
      </section>
    );
  }

  const totalCannabinoids = cannabinoids.reduce((acc, c) => acc + c.value, 0).toFixed(1);

  return (
    <section className="p-4 md:p-8 space-y-8 overflow-y-auto pb-28 md:pb-8">
      {/* ── Page Header ── */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-stone-500 mb-2">
            <span>Relatorios</span>
            <MaterialIcon icon="chevron_right" size="sm" />
            <span className="text-primary">Analise Ativa</span>
          </nav>
          <h2 className="text-2xl md:text-3xl font-black text-on-surface font-headline tracking-tight">
            Relatorio de Analise Laboratorial IA
          </h2>
          <p className="text-stone-500 font-medium text-sm">
            {patient.batchId} - Analise molecular e compatibilidade
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm">
            <MaterialIcon icon="share" size="sm" />
            <span className="hidden sm:inline ml-1">Compartilhar</span>
          </Button>
          <Button size="sm">
            <MaterialIcon icon="download" size="sm" />
            <span className="ml-1">Baixar PDF</span>
          </Button>
        </div>
      </div>

      {/* ── Patient Context Header ── */}
      <Card variant="glass" padding="md" className="rounded-3xl border-primary/10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <MaterialIcon icon="person" className="text-primary" size="lg" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-on-surface">{patient.name}</h3>
              <p className="text-xs text-stone-500">
                {patient.id} - {patient.condition}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge tone="primary">{patient.protocol}</Badge>
            <Badge tone="success">ATIVO</Badge>
          </div>
        </div>
      </Card>

      {/* ── Main Bento Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Analise Molecular - Cannabinoid Profile */}
        <div className="lg:col-span-8">
          <Card variant="glass" padding="lg" className="rounded-3xl relative overflow-hidden">
            <div className="absolute -bottom-10 -right-10 opacity-5 pointer-events-none">
              <span
                className="material-symbols-outlined text-[200px]"
                style={{ fontVariationSettings: "'wght' 100" }}
              >
                hub
              </span>
            </div>
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-8">
                <div>
                  <h3 className="text-xl font-bold text-primary font-headline">
                    Analise Molecular
                  </h3>
                  <p className="text-xs text-stone-500">
                    Composicao quimica e perfil de canabinoides
                  </p>
                </div>
                <Badge tone="primary">Hibrido Ativo</Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {/* Cannabinoid bars */}
                <div className="space-y-4">
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] uppercase tracking-widest text-stone-500">
                      Canabinoides (%)
                    </span>
                    <span className="text-2xl font-black text-on-surface">{totalCannabinoids}%</span>
                  </div>
                  <div className="space-y-3">
                    {cannabinoids.map((c) => (
                      <div key={c.name} className="space-y-1">
                        <div className="flex justify-between text-xs text-stone-300">
                          <span className="font-semibold">{c.name}</span>
                          <span className="text-primary">{c.value}%</span>
                        </div>
                        <ProgressBar value={c.pct} variant={c.color} glow size="md" />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Terpene Profile */}
                <div className="space-y-4">
                  <span className="text-[10px] uppercase tracking-widest text-stone-500">
                    Dominancia de Terpenos
                  </span>
                  <div className="grid grid-cols-2 gap-3">
                    {terpenes.map((t) => (
                      <div
                        key={t.name}
                        className="p-4 rounded-xl bg-white/5 border border-white/5 text-center"
                      >
                        <p className="text-[10px] uppercase text-stone-500 mb-1">{t.name}</p>
                        <p className="text-lg font-bold text-on-surface">
                          {t.value.split(" ")[0]}
                          <span className="text-xs font-normal text-stone-500 ml-0.5">mg/g</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Precisao do Modelo / Compatibility */}
        <div className="lg:col-span-4">
          <Card
            variant="glass"
            padding="lg"
            className="rounded-3xl border-2 border-primary/20 flex flex-col items-center justify-center text-center h-full"
          >
            <p className="text-[10px] uppercase tracking-widest text-stone-500 mb-6">
              Confiabilidade da Analise
            </p>
            <div className="relative flex items-center justify-center mb-6">
              <svg className="w-40 h-40 -rotate-90">
                <circle
                  className="text-surface-container-highest"
                  cx="80"
                  cy="80"
                  r="70"
                  fill="transparent"
                  stroke="currentColor"
                  strokeWidth="8"
                />
                <circle
                  className="text-primary"
                  cx="80"
                  cy="80"
                  r="70"
                  fill="transparent"
                  stroke="currentColor"
                  strokeDasharray={2 * Math.PI * 70}
                  strokeDashoffset={2 * Math.PI * 70 * (1 - confidence / 100)}
                  strokeLinecap="round"
                  strokeWidth="8"
                  style={{
                    filter: "drop-shadow(0 0 12px rgba(190,230,84,0.6))",
                  }}
                />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-4xl font-black text-on-surface tracking-tighter">
                  {confidence}%
                </span>
                <span className="text-[10px] font-bold text-primary uppercase tracking-widest">
                  Confianca
                </span>
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-stone-200">{patient.name}</p>
              <p className="text-xs text-stone-500 mt-1 max-w-[200px]">
                Proporcao otima de canabinoides para o protocolo de {patient.condition}.
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Interactions + Formulation ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Interacoes Medicamentosas */}
        <Card variant="glass" padding="lg" className="rounded-3xl">
          <div className="flex items-center gap-3 mb-6">
            <MaterialIcon icon="medication" className="text-primary" size="lg" />
            <div>
              <h3 className="text-lg font-bold text-on-surface font-headline">
                Interacoes Medicamentosas
              </h3>
              <p className="text-xs text-stone-500">Analise preditiva de interacoes</p>
            </div>
          </div>
          <div className="space-y-3">
            {interactions.map((interaction) => (
              <div
                key={interaction.drug}
                className={cn(
                  "p-4 rounded-xl border-l-4 bg-surface-container/50 border border-white/5",
                  interaction.severity === "danger"
                    ? "border-l-error"
                    : interaction.severity === "warning"
                      ? "border-l-amber-500"
                      : interaction.severity === "info"
                        ? "border-l-blue-400"
                        : "border-l-stone-600",
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-on-surface">{interaction.drug}</span>
                  <Badge tone={interaction.severity === "neutral" ? "neutral" : interaction.severity}>
                    {interaction.severity === "danger"
                      ? "ALTO RISCO"
                      : interaction.severity === "warning"
                        ? "MODERADO"
                        : interaction.severity === "info"
                          ? "BAIXO"
                          : "SEGURO"}
                  </Badge>
                </div>
                <p className="text-xs text-stone-400 leading-relaxed">{interaction.description}</p>
                <p className="text-[10px] text-stone-600 mt-1">{interaction.mechanism}</p>
              </div>
            ))}
          </div>
        </Card>

        {/* Recomendacao de Formulacao + Efeitos */}
        <div className="space-y-6">
          <Card variant="glass" padding="lg" className="rounded-3xl border-primary/10">
            <div className="flex items-center gap-3 mb-6">
              <MaterialIcon icon="science" className="text-primary" size="lg" />
              <h3 className="text-lg font-bold text-on-surface font-headline">
                Recomendacao de Formulacao
              </h3>
            </div>
            <div className="space-y-3">
              {Object.entries(formulation).map(([key, val]) => (
                <div key={key} className="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                  <span className="text-xs text-stone-500 uppercase tracking-wider">
                    {key === "product"
                      ? "Produto"
                      : key === "ratio"
                        ? "Proporcao"
                        : key === "concentration"
                          ? "Concentracao"
                          : key === "volume"
                            ? "Volume"
                            : key === "dosage"
                              ? "Posologia"
                              : "Perfil Terpenico"}
                  </span>
                  <span className="text-sm font-bold text-on-surface text-right max-w-[60%]">
                    {val}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          {/* Therapeutic Forecast */}
          <Card variant="glass" padding="md" className="rounded-3xl">
            <h4 className="text-sm font-bold text-stone-400 uppercase tracking-widest mb-4">
              Efeitos Esperados
            </h4>
            <div className="space-y-3">
              {effects.map((e) => (
                <div
                  key={e.label}
                  className="flex items-center gap-4 p-3 rounded-xl bg-surface-container-low border border-outline-variant/30"
                >
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                    <MaterialIcon icon={e.icon} className="text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-on-surface">{e.label}</p>
                    <p className="text-[10px] text-stone-500">{e.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* ── Evidencias Cientificas ── */}
      <Card variant="glass" padding="lg" className="rounded-3xl">
        <div className="flex items-center gap-3 mb-6">
          <MaterialIcon icon="menu_book" className="text-primary" size="lg" />
          <div>
            <h3 className="text-lg font-bold text-on-surface font-headline">
              Evidencias Cientificas
            </h3>
            <p className="text-xs text-stone-500">
              Fontes cientificas consultadas (PubMed/Cochrane)
            </p>
          </div>
        </div>
        <div className="space-y-3">
          {references.map((ref, i) => (
            <div
              key={ref.doi}
              className="p-4 rounded-xl bg-surface-container/50 border border-white/5 hover:border-primary/20 transition-all cursor-pointer flex items-start gap-4"
            >
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                <span className="text-xs font-black text-primary">{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-on-surface">{ref.title}</p>
                <p className="text-xs text-stone-500 mt-1">{ref.source}</p>
                <p className="text-[10px] text-stone-600 font-mono mt-1">DOI: {ref.doi}</p>
              </div>
              <MaterialIcon icon="open_in_new" size="sm" className="text-stone-500 flex-shrink-0" />
            </div>
          ))}
        </div>
      </Card>

      {/* ── Footer Stats ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card variant="glass" padding="sm" className="rounded-xl p-4">
          <span className="text-[10px] uppercase text-stone-500 tracking-widest">Data Colheita</span>
          <p className="text-sm font-bold text-on-surface mt-1">12 OUT, 2025</p>
        </Card>
        <Card variant="glass" padding="sm" className="rounded-xl p-4">
          <span className="text-[10px] uppercase text-stone-500 tracking-widest">Tempo Cura</span>
          <p className="text-sm font-bold text-on-surface mt-1">24 DIAS (FRIO)</p>
        </Card>
        <Card variant="glass" padding="sm" className="rounded-xl p-4">
          <span className="text-[10px] uppercase text-stone-500 tracking-widest">Tecnico Lab</span>
          <p className="text-sm font-bold text-on-surface mt-1">TECH_402_B</p>
        </Card>
        <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl">
          <span className="text-[10px] uppercase text-primary tracking-widest">Status do Lote</span>
          <p className="text-sm font-bold text-on-surface mt-1 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            PRONTO PARA DISPENSACAO
          </p>
        </div>
      </div>
    </section>
  );
}
