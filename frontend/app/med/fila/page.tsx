"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { listAttendances, createTriageLink, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceListItem } from "@/lib/types";
import {
  MaterialIcon,
  Badge,
  Button,
  SearchBar,
  StatCard,
} from "@/components/ui-tw";

/* ---------------------------------------------------------------------------
 * Types & helpers
 * --------------------------------------------------------------------------- */

type SortMode = "newest" | "oldest" | "risk";
type PriorityFilter = "all" | "critico" | "alto" | "moderado" | "baixo";
type StatusFilter = "all" | "pendente" | "em_revisao" | "revisado";

/** Map the real risk_level from backend to our UI keys. */
function deriveRiskLevel(item: AttendanceListItem): "critico" | "alto" | "moderado" | "baixo" {
  const raw = (item.risk_level ?? "").toLowerCase().trim();
  if (raw === "critical" || raw === "critico") return "critico";
  if (raw === "high" || raw === "alto") return "alto";
  if (raw === "moderate" || raw === "moderado") return "moderado";
  if (raw === "low" || raw === "baixo") return "baixo";
  // Fallback: sem dados de risco = baixo
  return "baixo";
}

const RISK_CONFIG = {
  critico: {
    label: "Critico",
    borderColor: "border-red-500",
    bgColor: "bg-red-950/40",
    textColor: "text-red-400",
    dotColor: "bg-red-500",
    badgeTone: "danger" as const,
    sortOrder: 0,
  },
  alto: {
    label: "Alto",
    borderColor: "border-orange-500",
    bgColor: "bg-orange-950/40",
    textColor: "text-orange-400",
    dotColor: "bg-orange-500",
    badgeTone: "warning" as const,
    sortOrder: 1,
  },
  moderado: {
    label: "Moderado",
    borderColor: "border-yellow-500",
    bgColor: "bg-yellow-950/40",
    textColor: "text-yellow-400",
    dotColor: "bg-yellow-500",
    badgeTone: "warning" as const,
    sortOrder: 2,
  },
  baixo: {
    label: "Baixo",
    borderColor: "border-emerald-500",
    bgColor: "bg-emerald-950/40",
    textColor: "text-emerald-400",
    dotColor: "bg-emerald-500",
    badgeTone: "success" as const,
    sortOrder: 3,
  },
} as const;

const STATUS_BADGE: Record<string, { label: string; tone: "primary" | "success" | "warning" | "danger" | "neutral" }> = {
  processado: { label: "Processado", tone: "success" },
  revisado: { label: "Revisado pelo medico", tone: "primary" },
  pendente: { label: "Aguardando revisao", tone: "warning" },
  em_revisao: { label: "Em Revisao", tone: "neutral" },
  erro: { label: "Erro", tone: "danger" },
};

/** Compute relative wait time from created_at timestamp. */
function formatWaitTime(createdAt: string): string {
  const now = Date.now();
  const created = new Date(createdAt).getTime();
  const diffMs = now - created;
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "agora";
  if (diffMin < 60) return `ha ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `ha ${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  return `ha ${diffD}d`;
}

/** Get patient initials for the avatar placeholder. */
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? "?";
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Normalise status values from backend into our filter keys. */
function normaliseStatus(status: string): string {
  return status.toLowerCase().replace(/\s+/g, "_").replace(/ã/g, "a").replace(/ç/g, "c");
}

/* ---------------------------------------------------------------------------
 * Component
 * --------------------------------------------------------------------------- */

export default function FilaDeAtendimentoPage() {
  const router = useRouter();
  const session = useApiSession();

  const [attendances, setAttendances] = useState<AttendanceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generatingLink, setGeneratingLink] = useState(false);
  const [linkFeedback, setLinkFeedback] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");

  // Auth redirect
  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      router.replace("/login");
    }
  }, [session.loading, session.data, router]);

  // Fetch attendances
  const fetchAttendances = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAttendances();
      setAttendances(data);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Falha ao carregar a fila.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session.data?.authenticated) {
      void fetchAttendances();
    }
  }, [session.data?.authenticated, fetchAttendances]);

  const handleGenerateTriageLink = useCallback(async () => {
    if (!session.data?.csrf_token) return;

    setGeneratingLink(true);
    setLinkFeedback(null);
    try {
      const link = await createTriageLink(session.data.csrf_token);
      await navigator.clipboard.writeText(link.url);
      setLinkFeedback(`Link de triagem copiado para ${link.clinic_label}.`);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Falha ao gerar link de triagem.";
      setLinkFeedback(msg);
    } finally {
      setGeneratingLink(false);
    }
  }, [session.data?.csrf_token]);

  // Derived data
  const filtered = useMemo(() => {
    let items = [...attendances];

    // Search
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      items = items.filter(
        (a) =>
          a.patient_name.toLowerCase().includes(q) ||
          a.phone.toLowerCase().includes(q),
      );
    }

    // Status filter
    if (statusFilter !== "all") {
      items = items.filter((a) => normaliseStatus(a.status) === statusFilter);
    }

    // Priority filter
    if (priorityFilter !== "all") {
      items = items.filter((a) => deriveRiskLevel(a) === priorityFilter);
    }

    // Sort
    items.sort((a, b) => {
      if (sortMode === "newest") return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (sortMode === "oldest") return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      // risk: higher risk first
      return RISK_CONFIG[deriveRiskLevel(a)].sortOrder - RISK_CONFIG[deriveRiskLevel(b)].sortOrder;
    });

    return items;
  }, [attendances, search, statusFilter, priorityFilter, sortMode]);

  // Stats
  const stats = useMemo(() => {
    const total = attendances.length;
    const aguardando = attendances.filter((a) => normaliseStatus(a.status) === "pendente").length;
    const emAtendimento = attendances.filter((a) => normaliseStatus(a.status) === "em_revisao").length;
    const finalizados = attendances.filter((a) => normaliseStatus(a.status) === "revisado").length;
    return { total, aguardando, emAtendimento, finalizados };
  }, [attendances]);

  // Show nothing while session loads
  if (session.loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6 lg:space-y-8">
      {/* ------------------------------------------------------------------ */}
      {/* Header */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-col gap-1">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-2xl lg:text-3xl font-headline font-bold text-on-surface leading-tight">
              Fila de Atendimento
            </h1>
            <p className="text-stone-500 text-sm flex items-center gap-2">
              <MaterialIcon icon="psychology" size="sm" className="text-primary" />
              Inteligencia Clinica
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon="link"
            loading={generatingLink}
            onClick={() => void handleGenerateTriageLink()}
            className="w-full lg:w-auto"
          >
            Gerar Link de Triagem
          </Button>
        </div>
        {linkFeedback ? (
          <p className="text-xs text-stone-400">{linkFeedback}</p>
        ) : null}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Stats row */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 lg:gap-4">
        <StatCard icon="group" label="Total na fila" value={stats.total} />
        <StatCard
          icon="hourglass_top"
          label="Aguardando"
          value={String(stats.aguardando).padStart(2, "0")}
          className="border-l-2 border-yellow-500/50"
        />
        <StatCard
          icon="stethoscope"
          label="Em atendimento"
          value={String(stats.emAtendimento).padStart(2, "0")}
          className="border-l-2 border-primary/50"
        />
        <StatCard
          icon="check_circle"
          label="Finalizados hoje"
          value={String(stats.finalizados).padStart(2, "0")}
          className="border-l-2 border-emerald-500/50"
        />
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Filter bar */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
        {/* Search */}
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar paciente por nome ou telefone..."
          className="flex-1 lg:max-w-sm"
        />

        {/* Filters row - scrollable on mobile */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0 -mx-1 px-1 no-scrollbar">
          {/* Status */}
          <FilterSelect
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as StatusFilter)}
            options={[
              { value: "all", label: "Status: Todos" },
              { value: "pendente", label: "Pendente" },
              { value: "em_revisao", label: "Em Revisao" },
              { value: "revisado", label: "Revisado" },
            ]}
          />

          {/* Priority */}
          <FilterSelect
            value={priorityFilter}
            onChange={(v) => setPriorityFilter(v as PriorityFilter)}
            options={[
              { value: "all", label: "Risco: Todos" },
              { value: "critico", label: "Critico" },
              { value: "alto", label: "Alto" },
              { value: "moderado", label: "Moderado" },
              { value: "baixo", label: "Baixo" },
            ]}
          />

          {/* Sort */}
          <FilterSelect
            value={sortMode}
            onChange={(v) => setSortMode(v as SortMode)}
            options={[
              { value: "newest", label: "Mais recente" },
              { value: "oldest", label: "Mais antigo" },
              { value: "risk", label: "Maior risco" },
            ]}
          />
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Queue list */}
      {/* ------------------------------------------------------------------ */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : error ? (
        <div className="glass-panel rounded-2xl p-8 text-center space-y-4">
          <MaterialIcon icon="error_outline" size="xl" className="text-error" />
          <p className="text-stone-400">{error}</p>
          <Button variant="secondary" size="sm" icon="refresh" onClick={fetchAttendances}>
            Tentar novamente
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        /* Empty state */
        <div className="glass-panel rounded-2xl p-12 text-center space-y-4 border border-white/5">
          <div className="w-20 h-20 mx-auto rounded-full bg-surface-container-high flex items-center justify-center">
            <MaterialIcon icon="event_available" size="xl" className="text-stone-600" />
          </div>
          <h3 className="text-lg font-headline font-bold text-stone-400">
            Nenhum paciente na fila
          </h3>
          <p className="text-sm text-stone-600 max-w-md mx-auto">
            Quando novos pacientes completarem a triagem pelo WhatsApp, eles aparecerao aqui automaticamente.
          </p>
        </div>
      ) : (
        <div className="space-y-3 lg:space-y-4">
          {filtered.map((item) => (
            <PatientQueueCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* Bottom padding for mobile nav */}
      <div className="h-20 lg:h-0" />
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * PatientQueueCard
 * --------------------------------------------------------------------------- */

function PatientQueueCard({ item }: { item: AttendanceListItem }) {
  const risk = deriveRiskLevel(item);
  const cfg = RISK_CONFIG[risk];
  const normStatus = normaliseStatus(item.status);
  const statusCfg = STATUS_BADGE[normStatus] ?? { label: item.status, tone: "neutral" as const };
  const waitTime = formatWaitTime(item.created_at);
  const initials = getInitials(item.patient_name);

  return (
    <div
      className={cn(
        "glass-panel rounded-2xl p-4 lg:p-6 border-l-4 transition-colors group",
        cfg.borderColor,
        "hover:bg-surface-container cursor-pointer",
      )}
    >
      {/* Desktop layout */}
      <div className="hidden lg:flex items-start justify-between gap-6">
        {/* Left: avatar + info */}
        <div className="flex gap-5 flex-1 min-w-0">
          {/* Avatar */}
          <div
            className={cn(
              "w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 border",
              "bg-surface-container-highest",
              `border-${risk === "critico" ? "red" : risk === "alto" ? "orange" : risk === "moderado" ? "yellow" : "emerald"}-500/20`,
            )}
          >
            <span className={cn("text-sm font-bold", cfg.textColor)}>{initials}</span>
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-lg font-bold text-on-surface truncate">
                {item.patient_name}
              </h3>
              <span className="text-xs text-stone-500 font-mono shrink-0">{item.phone}</span>
            </div>

            {/* Tags row */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Risk badge */}
              <span
                className={cn(
                  "px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border flex items-center gap-1.5",
                  cfg.bgColor,
                  cfg.textColor,
                  `border-${risk === "critico" ? "red" : risk === "alto" ? "orange" : risk === "moderado" ? "yellow" : "emerald"}-900/50`,
                )}
              >
                <span className={cn("w-1.5 h-1.5 rounded-full", cfg.dotColor)} />
                Risco {cfg.label}
              </span>

              {/* AI Status badge */}
              <Badge tone={statusCfg.tone}>{statusCfg.label}</Badge>

              {/* Wait time */}
              <span className="px-3 py-1 bg-surface-container-high text-stone-400 text-[10px] font-bold rounded-full border border-white/5 flex items-center gap-1">
                <MaterialIcon icon="schedule" size="sm" className="text-[10px]" />
                {waitTime}
              </span>

              {/* Queixa principal */}
              {item.main_complaint ? (
                <span className="text-[10px] text-stone-400 italic truncate max-w-[200px]">
                  {item.main_complaint}
                </span>
              ) : null}

              {/* Fontes consultadas */}
              <span className="text-[10px] text-stone-500 font-mono">
                {item.rag_chunks_used} fontes consultadas
              </span>

              {/* Modelo de analise */}
              <span className="text-[10px] text-stone-500 font-mono hidden xl:inline">
                Modelo: {item.report_model}
              </span>
            </div>
          </div>
        </div>

        {/* Right: action */}
        <div className="shrink-0 flex items-center gap-4">
          <Link href={`/med/consulta/${item.id}`}>
            <Button
              size="sm"
              icon="play_arrow"
              className="opacity-80 group-hover:opacity-100 transition-opacity"
            >
              Atender
            </Button>
          </Link>
        </div>
      </div>

      {/* Mobile layout */}
      <div className="lg:hidden space-y-3">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div
            className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center shrink-0 border",
              "bg-surface-container",
              `border-${risk === "critico" ? "red" : risk === "alto" ? "orange" : risk === "moderado" ? "yellow" : "emerald"}-500/30`,
            )}
          >
            <span className={cn("text-xs font-bold", cfg.textColor)}>{initials}</span>
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <h4 className="font-bold text-sm text-on-surface truncate">{item.patient_name}</h4>
              <span
                className={cn(
                  "text-[10px] font-bold px-2 py-0.5 rounded border shrink-0",
                  cfg.bgColor,
                  cfg.textColor,
                  `border-${risk === "critico" ? "red" : risk === "alto" ? "orange" : risk === "moderado" ? "yellow" : "emerald"}-900/50`,
                )}
              >
                {cfg.label.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-stone-500 mt-0.5 truncate">{item.phone}</p>

            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <Badge tone={statusCfg.tone} className="text-[9px]">{statusCfg.label}</Badge>
              <span className="flex items-center gap-1 text-[10px] text-stone-500">
                <MaterialIcon icon="schedule" size="sm" className="text-[11px]" />
                {waitTime}
              </span>
              <span className="text-[10px] text-stone-600 font-mono">
                {item.rag_chunks_used} fontes
              </span>
            </div>
          </div>
        </div>

        {/* Action */}
        <Link href={`/med/consulta/${item.id}`} className="block">
          <Button
            size="sm"
            icon="play_arrow"
            className="w-full"
          >
            Atender
          </Button>
        </Link>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------------
 * FilterSelect - small custom select for filter bar
 * --------------------------------------------------------------------------- */

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "appearance-none bg-surface-container-high border border-white/5 rounded-lg",
        "px-3 py-2 text-xs text-on-surface-variant font-semibold",
        "focus:border-primary-container focus:outline-none transition-colors cursor-pointer",
        "whitespace-nowrap shrink-0",
      )}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
