"use client";

import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { listAgents, getAgentDiary, ApiError } from "@/lib/api";
import { Card, Badge, Button, StatCard, MaterialIcon } from "@/components/ui-tw";

/* ================================================================== */
/*  TYPES                                                              */
/* ================================================================== */

interface AgentSkill {
  name: string;
  description: string;
}

interface AgentInfo {
  name: string;
  class: string;
  description: string;
  palace_room?: string;
  skills_count?: number;
  skills?: AgentSkill[];
  diary_entries?: number;
  status: string;
  error?: string;
}

interface DiaryEntry {
  timestamp?: string;
  event?: string;
  details?: string;
  [key: string]: unknown;
}

/* ================================================================== */
/*  CONSTANTS                                                          */
/* ================================================================== */

const AGENT_ICONS: Record<string, string> = {
  AgenteTriagem: "assignment_turned_in",
  AgenteAnamnese: "clinical_notes",
  AgenteTratamento: "medication_liquid",
  AgentePrescritor: "medication",
  AgenteCientifico: "science",
  AgenteRegulatorio: "gavel",
  AgenteFollowUp: "follow_the_signs",
  AgenteExtrator: "search",
};

const AGENT_KEYS: Record<string, string> = {
  AgenteTriagem: "triagem",
  AgenteAnamnese: "anamnese",
  AgenteTratamento: "tratamento",
  AgentePrescritor: "prescritor",
  AgenteCientifico: "cientifico",
  AgenteRegulatorio: "regulatorio",
  AgenteFollowUp: "follow_up",
  AgenteExtrator: "extrator",
};

function statusTone(s: string): "success" | "danger" | "warning" | "neutral" {
  if (s === "active") return "success";
  if (s === "error") return "danger";
  return "neutral";
}

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function AgentesPage() {
  const session = useApiSession();

  /* ── State ── */
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [diaryLoading, setDiaryLoading] = useState<string | null>(null);
  const [diaryData, setDiaryData] = useState<Record<string, DiaryEntry[]>>({});

  /* ── Fetch agents ── */
  const fetchAgents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAgents();
      setAgents((data ?? []) as unknown as AgentInfo[]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Falha ao carregar agentes.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAgents();
  }, [fetchAgents]);

  /* ── Fetch diary for an agent ── */
  async function handleToggleDiary(agent: AgentInfo) {
    const key = AGENT_KEYS[agent.class] ?? agent.class;
    if (expandedAgent === agent.class) {
      setExpandedAgent(null);
      return;
    }
    setExpandedAgent(agent.class);

    if (diaryData[key]) return; // already loaded

    setDiaryLoading(key);
    try {
      const data = await getAgentDiary(key, 10);
      setDiaryData((prev) => ({ ...prev, [key]: (data ?? []) as DiaryEntry[] }));
    } catch {
      setDiaryData((prev) => ({ ...prev, [key]: [] }));
    } finally {
      setDiaryLoading(null);
    }
  }

  /* ── Derived stats ── */
  const totalAgents = agents.length;
  const activeAgents = agents.filter((a) => a.status === "active").length;
  const totalSkills = agents.reduce((sum, a) => sum + (a.skills_count ?? 0), 0);
  const totalDiary = agents.reduce((sum, a) => sum + (a.diary_entries ?? 0), 0);

  /* ================================================================ */
  /*  RENDER                                                           */
  /* ================================================================ */

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-on-surface mb-2">
            Agentes de <span className="text-primary">IA</span>
            <span className="text-on-surface-variant font-bold text-lg md:text-xl ml-2">
              e Habilidades
            </span>
          </h1>
          <p className="text-on-surface-variant max-w-xl">
            Gerencie e monitore os agentes especializados do pipeline clinico. Cada agente possui
            habilidades unicas e um diario de atividades.
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <Button
            variant="ghost"
            icon="refresh"
            size="sm"
            onClick={() => {
              setDiaryData({});
              setExpandedAgent(null);
              void fetchAgents();
            }}
            loading={loading}
          >
            Atualizar
          </Button>
        </div>
      </header>

      {/* ── Error state ── */}
      {error && (
        <Card variant="outline" padding="md" className="border-error/30">
          <div className="flex items-center gap-3">
            <MaterialIcon icon="error" className="text-error" />
            <div>
              <p className="text-sm font-bold text-error">Erro ao carregar dados</p>
              <p className="text-xs text-on-surface-variant">{error}</p>
            </div>
            <Button
              variant="danger"
              size="sm"
              className="ml-auto"
              onClick={() => {
                setError(null);
                void fetchAgents();
              }}
            >
              Tentar novamente
            </Button>
          </div>
        </Card>
      )}

      {/* ── Loading skeleton ── */}
      {loading && !agents.length && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass-panel rounded-2xl p-5 h-28 animate-pulse" />
          ))}
        </div>
      )}

      {/* ── KPIs ── */}
      {!loading && agents.length > 0 && (
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon="smart_toy" label="Total de Agentes" value={String(totalAgents)} />
          <StatCard icon="check_circle" label="Agentes Ativos" value={String(activeAgents)} />
          <StatCard icon="psychology" label="Total de Habilidades" value={String(totalSkills)} />
          <StatCard icon="auto_stories" label="Entradas no Diario" value={String(totalDiary)} />
        </section>
      )}

      {/* ── Agent Cards Grid ── */}
      {!loading && agents.length > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {agents.map((agent) => {
            const agentKey = AGENT_KEYS[agent.class] ?? agent.class;
            const isExpanded = expandedAgent === agent.class;
            const icon = AGENT_ICONS[agent.class] ?? "smart_toy";
            const diary = diaryData[agentKey];
            const isDiaryLoading = diaryLoading === agentKey;

            return (
              <Card
                key={agent.class}
                variant="glass"
                padding="md"
                className={cn(
                  "transition-all duration-300 cursor-pointer",
                  isExpanded && "ring-1 ring-primary/30",
                )}
              >
                {/* ── Card Header ── */}
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                      <MaterialIcon icon={icon} filled className="text-primary text-2xl" />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold font-headline text-on-surface">
                        {agent.name}
                      </h3>
                      <p className="text-xs text-on-surface-variant line-clamp-2">
                        {agent.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 mt-1">
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full",
                        agent.status === "active" ? "bg-emerald-400" : "bg-red-400",
                      )}
                    />
                    <span className="text-[10px] text-stone-500 uppercase tracking-widest font-bold">
                      {agent.status}
                    </span>
                  </div>
                </div>

                {/* ── Badges ── */}
                <div className="flex items-center gap-2 flex-wrap mb-4">
                  {agent.palace_room && (
                    <Badge tone="neutral">
                      <MaterialIcon icon="meeting_room" size="sm" className="mr-1" />
                      {agent.palace_room}
                    </Badge>
                  )}
                  <Badge tone="success">
                    {agent.skills_count ?? 0} habilidade{(agent.skills_count ?? 0) !== 1 ? "s" : ""}
                  </Badge>
                  {(agent.diary_entries ?? 0) > 0 && (
                    <Badge tone="neutral">
                      {agent.diary_entries} registro{(agent.diary_entries ?? 0) !== 1 ? "s" : ""}
                    </Badge>
                  )}
                  {agent.error && <Badge tone="danger">Erro</Badge>}
                </div>

                {/* ── Skills List ── */}
                {agent.skills && agent.skills.length > 0 && (
                  <div className="mb-4">
                    <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold mb-2">
                      Habilidades
                    </p>
                    <div className="space-y-1.5">
                      {agent.skills.map((skill) => (
                        <div
                          key={skill.name}
                          className="flex items-center gap-2 p-2 bg-white/5 rounded-lg"
                        >
                          <MaterialIcon icon="bolt" size="sm" className="text-primary/70" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-on-surface truncate">
                              {skill.name}
                            </p>
                            <p className="text-[10px] text-stone-500 truncate">
                              {skill.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* ── Actions ── */}
                <div className="flex gap-2 pt-2 border-t border-white/5">
                  <Button
                    variant={isExpanded ? "primary" : "secondary"}
                    size="sm"
                    icon="auto_stories"
                    onClick={() => void handleToggleDiary(agent)}
                    loading={isDiaryLoading}
                  >
                    {isExpanded ? "Fechar Diario" : "Ver Diario"}
                  </Button>
                </div>

                {/* ── Expanded Diary Section ── */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-white/5">
                    <p className="text-[10px] text-stone-500 uppercase tracking-widest font-bold mb-3">
                      Diario Recente
                    </p>
                    {isDiaryLoading && (
                      <div className="flex items-center gap-2 text-stone-500 text-sm">
                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                        Carregando...
                      </div>
                    )}
                    {!isDiaryLoading && diary && diary.length === 0 && (
                      <p className="text-sm text-stone-500">Nenhuma entrada no diario.</p>
                    )}
                    {!isDiaryLoading && diary && diary.length > 0 && (
                      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                        {diary.map((entry, idx) => (
                          <div key={idx} className="p-3 bg-white/5 rounded-lg">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-bold text-on-surface">
                                {entry.event ?? "Evento"}
                              </span>
                              {entry.timestamp && (
                                <span className="text-[10px] text-stone-500">
                                  {new Date(entry.timestamp).toLocaleString("pt-BR", {
                                    day: "2-digit",
                                    month: "2-digit",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  })}
                                </span>
                              )}
                            </div>
                            {entry.details && (
                              <p className="text-xs text-stone-400 line-clamp-3">{entry.details}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </Card>
            );
          })}
        </section>
      )}

      {/* ── Empty state ── */}
      {!loading && !error && agents.length === 0 && (
        <Card variant="glass" padding="lg">
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mb-4">
              <MaterialIcon icon="smart_toy" filled className="text-primary text-3xl" />
            </div>
            <h3 className="text-lg font-bold font-headline text-on-surface mb-2">
              Nenhum agente encontrado
            </h3>
            <p className="text-sm text-on-surface-variant max-w-md">
              Os agentes de IA nao puderam ser carregados. Verifique a configuracao do backend.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
