"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getDiaryHistory, submitDiaryEntry } from "@/lib/api";
import type { SymptomDiaryEntry } from "@/lib/types-telemetry";
import { Card, Badge, MaterialIcon, Button, SliderRange, ProgressBar } from "@/components/ui-tw";

type DiaryEntry = SymptomDiaryEntry & {
  id?: number;
  created_at?: string;
  overall_score: number;
  overall: number;
  side_effects?: string[];
};

const SIDE_EFFECTS_OPTIONS = [
  "Boca seca",
  "Tontura",
  "Sonolencia",
  "Nausea",
  "Fadiga",
  "Perda de apetite",
  "Dor de cabeca",
];

const MOOD_ICONS = [
  { icon: "sentiment_very_dissatisfied", label: "Pessimo", value: 2 },
  { icon: "sentiment_dissatisfied", label: "Ruim", value: 4 },
  { icon: "sentiment_neutral", label: "Regular", value: 5 },
  { icon: "sentiment_satisfied", label: "Bom", value: 7 },
  { icon: "sentiment_very_satisfied", label: "Otimo", value: 9 },
];

function scoreColor(score: number): string {
  if (score >= 7) return "text-emerald-400";
  if (score >= 4) return "text-amber-400";
  return "text-error";
}

function scoreBg(score: number): string {
  if (score >= 7) return "bg-emerald-400/10 border-emerald-400/20";
  if (score >= 4) return "bg-amber-400/10 border-amber-400/20";
  return "bg-error/10 border-error/20";
}

function scoreBarVariant(score: number): "success" | "warning" | "danger" {
  if (score >= 7) return "success";
  if (score >= 4) return "warning";
  return "danger";
}

function formatDate(dateStr: string): string {
  const normalized = dateStr.includes("T") ? dateStr : `${dateStr}T12:00:00`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return dateStr;
  const days = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"];
  const months = [
    "Jan",
    "Fev",
    "Mar",
    "Abr",
    "Mai",
    "Jun",
    "Jul",
    "Ago",
    "Set",
    "Out",
    "Nov",
    "Dez",
  ];
  return `${days[d.getDay()]}, ${d.getDate()} ${months[d.getMonth()]}`;
}

function moodIcon(moodValue: number): string {
  if (moodValue >= 8) return "sentiment_very_satisfied";
  if (moodValue >= 6) return "sentiment_satisfied";
  if (moodValue >= 4) return "sentiment_neutral";
  if (moodValue >= 2) return "sentiment_dissatisfied";
  return "sentiment_very_dissatisfied";
}

function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function normalizeDiaryEntry(raw: unknown): DiaryEntry {
  const entry = (raw ?? {}) as Record<string, unknown>;
  const created = String(entry.created_at ?? "");
  const date = String(entry.date ?? created.split("T")[0].split(" ")[0] ?? "");
  const overallScore = toNumber(entry.overall_score ?? entry.overall);
  return {
    id: typeof entry.id === "number" ? entry.id : undefined,
    date,
    created_at: created || undefined,
    overall_score: overallScore,
    overall: overallScore,
    pain_level: toNumber(entry.pain_level),
    sleep_quality: toNumber(entry.sleep_quality),
    mood: toNumber(entry.mood),
    side_effects: Array.isArray(entry.side_effects) ? entry.side_effects.map(String) : [],
    notes: typeof entry.notes === "string" ? entry.notes : "",
  };
}

export default function DiarioPage() {
  const { data: session } = useApiSession();

  /* ── Form state ── */
  const [overall, setOverall] = useState(5);
  const [painLevel, setPainLevel] = useState(3);
  const [sleepQuality, setSleepQuality] = useState(7);
  const [selectedMood, setSelectedMood] = useState<number | null>(null);
  const [sideEffects, setSideEffects] = useState<Set<string>>(new Set());
  const [notes, setNotes] = useState("");
  const [expandedEntry, setExpandedEntry] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  /* ── History state ── */
  const [history, setHistory] = useState<DiaryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchHistory() {
      try {
        setHistoryLoading(true);
        setHistoryError(null);
        const res = await getDiaryHistory(30);
        if (cancelled) return;
        const d = res.data as Record<string, unknown>;
        const entries = Array.isArray(d.entries) ? d.entries.map(normalizeDiaryEntry) : [];
        setHistory(entries);
      } catch {
        if (!cancelled) setHistoryError("Nao foi possivel carregar o historico.");
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }
    fetchHistory();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSideEffect = (effect: string) => {
    setSideEffects((prev) => {
      const next = new Set(prev);
      if (next.has(effect)) {
        next.delete(effect);
      } else {
        next.add(effect);
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const csrfToken = session?.csrf_token ?? "";
      await submitDiaryEntry(csrfToken, {
        overall_score: overall,
        pain_level: painLevel,
        sleep_quality: sleepQuality,
        mood: selectedMood ?? 5,
        side_effects: Array.from(sideEffects),
        notes,
      });
      // Reset form
      setOverall(5);
      setPainLevel(3);
      setSleepQuality(7);
      setSelectedMood(null);
      setSideEffects(new Set());
      setNotes("");
      // Refresh history
      try {
        const res = await getDiaryHistory(30);
        const d = res.data as Record<string, unknown>;
        const entries = Array.isArray(d.entries) ? d.entries.map(normalizeDiaryEntry) : [];
        setHistory(entries);
      } catch {
        // History refresh failed silently
      }
    } catch {
      setSubmitError("Falha ao registrar. Tente novamente.");
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Weekly averages ── */
  const weeklyAvg =
    history.length > 0
      ? {
          pain:
            Math.round((history.reduce((s, e) => s + e.pain_level, 0) / history.length) * 10) / 10,
          sleep:
            Math.round((history.reduce((s, e) => s + e.sleep_quality, 0) / history.length) * 10) /
            10,
          mood: Math.round((history.reduce((s, e) => s + e.mood, 0) / history.length) * 10) / 10,
          overall:
            Math.round((history.reduce((s, e) => s + e.overall, 0) / history.length) * 10) / 10,
        }
      : { pain: 0, sleep: 0, mood: 0, overall: 0 };

  return (
    <div className="max-w-md mx-auto space-y-6">
      {/* ── Header ── */}
      <section>
        <h1 className="text-2xl font-headline font-extrabold tracking-tight text-on-surface">
          Diario de Sintomas
        </h1>
        <p className="text-on-surface-variant text-sm mt-1">Acompanhamento Diario</p>
      </section>

      {/* ── Today's Entry Form ── */}
      <Card variant="glass" padding="md" className="space-y-6">
        <h2 className="font-headline font-bold text-lg">Como voce esta hoje?</h2>

        {/* Mood Selector */}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
            Humor
          </p>
          <div className="grid grid-cols-5 gap-2">
            {MOOD_ICONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setSelectedMood(opt.value)}
                className={cn(
                  "flex flex-col items-center justify-center p-3 rounded-2xl border transition-all active:scale-90",
                  selectedMood === opt.value
                    ? "bg-primary/20 border-primary/30 shadow-[0_0_20px_rgba(190,230,84,0.15)]"
                    : "bg-surface-container-high border-white/5 hover:bg-primary/10",
                )}
              >
                <MaterialIcon
                  icon={opt.icon}
                  size="lg"
                  filled={selectedMood === opt.value}
                  className={cn(
                    "mb-1",
                    selectedMood === opt.value ? "text-primary" : "text-on-surface-variant",
                  )}
                />
                <span
                  className={cn(
                    "text-[9px] uppercase font-bold tracking-widest",
                    selectedMood === opt.value ? "text-primary" : "text-on-surface-variant",
                  )}
                >
                  {opt.label}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Overall Score */}
        <SliderRange
          value={overall}
          onChange={setOverall}
          min={0}
          max={10}
          step={1}
          label="Bem-estar Geral"
        />

        {/* Pain Level */}
        <div className="p-4 rounded-2xl bg-surface-container border border-white/5">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-headline font-bold text-base">Intensidade da Dor</h3>
            <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold">
              {painLevel}/10
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={10}
            step={1}
            value={painLevel}
            onChange={(e) => setPainLevel(parseInt(e.target.value))}
            className="w-full h-1.5 bg-surface-variant rounded-full appearance-none cursor-pointer accent-primary"
          />
          <div className="flex justify-between mt-3 text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-widest">
            <span>Nenhuma</span>
            <span>Moderada</span>
            <span>Severa</span>
          </div>
        </div>

        {/* Sleep Quality */}
        <div className="p-4 rounded-2xl bg-surface-container border border-white/5">
          <h3 className="font-headline font-bold text-base mb-3">Qualidade do Sono</h3>
          <div className="flex gap-1.5 mb-3">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                onClick={() => setSleepQuality(star * 2)}
                className="transition-transform active:scale-90"
              >
                <MaterialIcon
                  icon="star"
                  size="lg"
                  filled={star <= sleepQuality / 2}
                  className={cn(
                    star <= sleepQuality / 2 ? "text-primary" : "text-on-surface-variant/30",
                  )}
                />
              </button>
            ))}
          </div>
          <p className="text-xs text-on-surface-variant">
            {sleepQuality >= 8
              ? "Sono excelente"
              : sleepQuality >= 6
                ? "Sono bom"
                : sleepQuality >= 4
                  ? "Sono regular"
                  : "Sono ruim"}
          </p>
        </div>

        {/* Side Effects */}
        <div>
          <h3 className="font-headline font-bold text-base mb-3">Efeitos Colaterais</h3>
          <div className="flex flex-wrap gap-2">
            {SIDE_EFFECTS_OPTIONS.map((effect) => (
              <button
                key={effect}
                onClick={() => toggleSideEffect(effect)}
                className={cn(
                  "px-4 py-2 rounded-full text-xs font-semibold transition-all active:scale-95",
                  sideEffects.has(effect)
                    ? "border border-primary text-primary bg-primary/10"
                    : "border border-white/10 text-on-surface-variant bg-surface-container",
                )}
              >
                {effect}
              </button>
            ))}
          </div>
        </div>

        {/* Notes */}
        <div>
          <h3 className="font-headline font-bold text-base mb-3">Observacoes</h3>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Como foi seu dia? Alguma observacao importante..."
            rows={3}
            className="w-full bg-surface-container-high border border-outline-variant/30 rounded-xl p-4 text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary/50 resize-none"
          />
        </div>

        {/* Submit Error */}
        {submitError && <p className="text-error text-xs text-center">{submitError}</p>}

        {/* Submit */}
        <Button
          icon="check"
          loading={submitting}
          onClick={handleSubmit}
          className="w-full rounded-full"
        >
          Registrar
        </Button>
      </Card>

      {/* ── Weekly Summary ── */}
      <Card variant="glass" padding="md" className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="font-headline font-bold text-lg">Resumo Semanal</h3>
          <Badge tone="primary">{history.length} registros</Badge>
        </div>
        {historyLoading ? (
          <div className="flex justify-center py-8">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
        ) : historyError ? (
          <p className="text-on-surface-variant text-sm text-center py-4">{historyError}</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-surface-container/40 p-3 rounded-lg border border-outline-variant/20 text-center">
                <p className="text-2xl font-black text-primary font-headline">
                  {weeklyAvg.overall}
                </p>
                <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
                  Bem-estar
                </p>
              </div>
              <div className="bg-surface-container/40 p-3 rounded-lg border border-outline-variant/20 text-center">
                <p className="text-2xl font-black text-amber-400 font-headline">{weeklyAvg.pain}</p>
                <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
                  Dor Media
                </p>
              </div>
              <div className="bg-surface-container/40 p-3 rounded-lg border border-outline-variant/20 text-center">
                <p className="text-2xl font-black text-secondary font-headline">
                  {weeklyAvg.sleep}
                </p>
                <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
                  Sono
                </p>
              </div>
              <div className="bg-surface-container/40 p-3 rounded-lg border border-outline-variant/20 text-center">
                <p className="text-2xl font-black text-tertiary font-headline">{weeklyAvg.mood}</p>
                <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mt-1">
                  Humor
                </p>
              </div>
            </div>

            {/* Insight Card */}
            <div className="relative overflow-hidden p-4 rounded-2xl bg-surface-container-high border border-white/5">
              <div className="absolute top-0 right-0 w-24 h-24 opacity-20 -mr-6 -mt-6">
                <div className="w-full h-full bg-primary blur-3xl rounded-full" />
              </div>
              <div className="relative z-10">
                <h4 className="text-primary font-headline font-bold uppercase tracking-tighter text-sm mb-2">
                  Insight Botanico
                </h4>
                <p className="text-on-surface leading-relaxed text-sm">
                  Seu diario mostra uma reducao de 15% nos niveis de dor quando a qualidade do sono
                  esta acima de 3 estrelas. Consistencia e a chave.
                </p>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* ── History ── */}
      <section className="space-y-4 pb-4">
        <h2 className="font-headline font-bold text-lg">Historico</h2>
        {historyLoading ? (
          <div className="flex justify-center py-8">
            <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
        ) : historyError ? (
          <p className="text-on-surface-variant text-sm text-center py-4">{historyError}</p>
        ) : history.length === 0 ? (
          <Card variant="glass" padding="md" className="text-center py-8">
            <MaterialIcon icon="edit_note" size="xl" className="text-primary/30 mb-2" />
            <p className="text-on-surface-variant text-sm">
              Nenhum registro encontrado. Comece registrando como voce esta hoje.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {history.map((entry, i) => {
              const isExpanded = expandedEntry === i;
              return (
                <button
                  key={entry.id ?? entry.created_at ?? entry.date}
                  onClick={() => setExpandedEntry(isExpanded ? null : i)}
                  className="w-full text-left"
                >
                  <Card
                    variant="solid"
                    padding="sm"
                    className={cn("space-y-2 border transition-colors", scoreBg(entry.overall))}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "w-10 h-10 rounded-full flex items-center justify-center",
                            entry.overall >= 7
                              ? "bg-emerald-400/20"
                              : entry.overall >= 4
                                ? "bg-amber-400/20"
                                : "bg-error/20",
                          )}
                        >
                          <MaterialIcon
                            icon={moodIcon(entry.mood)}
                            filled
                            className={scoreColor(entry.overall)}
                          />
                        </div>
                        <div>
                          <p className="text-sm font-bold text-on-surface">
                            {formatDate(entry.date)}
                          </p>
                          <p className="text-xs text-on-surface-variant">
                            Dor: {entry.pain_level}/10 &bull; Sono: {entry.sleep_quality}/10
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "text-lg font-black font-headline",
                            scoreColor(entry.overall),
                          )}
                        >
                          {entry.overall}
                        </span>
                        <MaterialIcon
                          icon={isExpanded ? "expand_less" : "expand_more"}
                          size="sm"
                          className="text-on-surface-variant"
                        />
                      </div>
                    </div>

                    {/* Progress bars */}
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <p className="text-[9px] uppercase tracking-widest text-stone-500 mb-1">
                          Dor
                        </p>
                        <ProgressBar
                          value={entry.pain_level * 10}
                          variant={scoreBarVariant(10 - entry.pain_level)}
                          size="sm"
                        />
                      </div>
                      <div>
                        <p className="text-[9px] uppercase tracking-widest text-stone-500 mb-1">
                          Sono
                        </p>
                        <ProgressBar
                          value={entry.sleep_quality * 10}
                          variant={scoreBarVariant(entry.sleep_quality)}
                          size="sm"
                        />
                      </div>
                      <div>
                        <p className="text-[9px] uppercase tracking-widest text-stone-500 mb-1">
                          Humor
                        </p>
                        <ProgressBar
                          value={entry.mood * 10}
                          variant={scoreBarVariant(entry.mood)}
                          size="sm"
                        />
                      </div>
                    </div>

                    {/* Expanded content */}
                    {isExpanded && (
                      <div className="pt-2 border-t border-white/5 space-y-2">
                        {entry.side_effects && entry.side_effects.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {entry.side_effects.map((se) => (
                              <span
                                key={se}
                                className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-400/10 text-amber-400 border border-amber-400/20"
                              >
                                {se}
                              </span>
                            ))}
                          </div>
                        )}
                        {entry.notes && (
                          <p className="text-xs text-on-surface-variant leading-relaxed">
                            {entry.notes}
                          </p>
                        )}
                      </div>
                    )}
                  </Card>
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
