"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

import {
  Button,
  Badge,
  Card,
  MaterialIcon,
  StatCard,
  Input,
  ProgressBar,
} from "@/components/ui-tw";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import {
  listCampaignTemplates,
  listCampaignExecutions,
  createCampaignTemplate,
  activateCampaignTemplate,
  sendCampaign,
} from "@/lib/api";
import type {
  CampaignTemplate,
  CampaignTemplateStatus,
  CampaignChannel,
  CampaignExecution,
  CampaignExecutionStatus,
} from "@/lib/types-campaign";

/* ── helpers ───────────────────────────────────────────────────────── */

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/** Map backend execution record (target_count) to frontend type (total_patients). */
function mapExecution(raw: Record<string, unknown>): CampaignExecution {
  return {
    id: raw.id as number,
    template_id: raw.template_id as number,
    clinic_id: (raw.clinic_id as number) ?? 0,
    status: raw.status as CampaignExecutionStatus,
    total_patients: (raw.target_count as number) ?? 0,
    sent_count: (raw.sent_count as number) ?? 0,
    failed_count: (raw.failed_count as number) ?? 0,
    triggered_by: (raw.triggered_by as number) ?? 0,
    started_at: (raw.started_at as string) ?? new Date().toISOString(),
    completed_at: (raw.completed_at as string | null) ?? null,
  };
}

const channelConfig: Record<CampaignChannel, { icon: string; label: string; color: string }> = {
  whatsapp: { icon: "chat", label: "WhatsApp", color: "text-emerald-400 bg-emerald-400/10" },
  email: { icon: "email", label: "Email", color: "text-blue-400 bg-blue-400/10" },
  sms: { icon: "sms", label: "SMS", color: "text-amber-400 bg-amber-400/10" },
};

const templateStatusConfig: Record<
  CampaignTemplateStatus,
  { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }
> = {
  active: { tone: "success", label: "Ativo" },
  draft: { tone: "warning", label: "Rascunho" },
  archived: { tone: "neutral", label: "Arquivado" },
};

const executionStatusConfig: Record<
  CampaignExecutionStatus,
  { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }
> = {
  pending: { tone: "warning", label: "Pendente" },
  in_progress: { tone: "primary", label: "Em Progresso" },
  completed: { tone: "success", label: "Concluido" },
  failed: { tone: "danger", label: "Falhou" },
};

/* ── new template modal ────────────────────────────────────────────── */
function NewTemplateModal({
  open,
  onClose,
  onCreated,
  csrfToken,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (t: CampaignTemplate) => void;
  csrfToken: string;
}) {
  const [name, setName] = useState("");
  const [channel, setChannel] = useState<CampaignChannel>("whatsapp");
  const [body, setBody] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !body.trim()) {
      setFormError("Nome e corpo da mensagem sao obrigatorios.");
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      const res = await createCampaignTemplate(csrfToken, {
        name: name.trim(),
        template_body: body.trim(),
        channel,
      });
      const created = res.data as unknown as CampaignTemplate;
      onCreated(created);
      onClose();
      setName("");
      setBody("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao criar modelo.";
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-white transition-colors"
        >
          <MaterialIcon icon="close" />
        </button>
        <h3 className="text-xl font-bold font-headline mb-6">Novo Modelo de Mensagem</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nome do Modelo"
            icon="description"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ex: Lembrete de Consulta"
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Canal
            </label>
            <div className="flex gap-3">
              {(["whatsapp", "email", "sms"] as CampaignChannel[]).map((ch) => {
                const cfg = channelConfig[ch];
                return (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => setChannel(ch)}
                    className={cn(
                      "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors",
                      channel === ch
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-outline-variant/30 text-stone-400 hover:bg-white/5",
                    )}
                  >
                    <MaterialIcon icon={cfg.icon} size="sm" />
                    {cfg.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Corpo da Mensagem
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Ola, {{patient_name}}! ..."
              rows={5}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface placeholder:text-stone-600 focus:border-primary-container focus:outline-none transition-colors resize-none"
            />
            <span className="text-[10px] text-stone-500">
              Campos disponiveis: {"{{patient_name}}"}, {"{{doctor_name}}"}, {"{{product_name}}"},{" "}
              {"{{clinic_name}}"}
            </span>
          </div>
          {formError && <p className="text-sm text-error">{formError}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" icon="add_circle" disabled={submitting}>
              {submitting ? "Criando..." : "Criar Modelo"}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── page ───────────────────────────────────────────────────────────── */
export default function CampanhasPage() {
  const router = useRouter();
  const session = useApiSession();
  const [activeTab, setActiveTab] = useState<"templates" | "executions">("templates");
  const [templates, setTemplates] = useState<CampaignTemplate[]>([]);
  const [executions, setExecutions] = useState<CampaignExecution[]>([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  const csrfToken = session.data?.csrf_token ?? "";

  const fetchData = useCallback(async () => {
    setDataLoading(true);
    try {
      const [tplRaw, execRaw] = await Promise.all([
        listCampaignTemplates(),
        listCampaignExecutions(),
      ]);
      setTemplates((tplRaw ?? []) as unknown as CampaignTemplate[]);
      setExecutions((execRaw ?? []).map(mapExecution));
    } catch {
      // silently degrade -- empty lists shown
    } finally {
      setDataLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!session.loading) {
      fetchData();
    }
  }, [session.loading, fetchData]);

  /* stats */
  const activeTemplates = templates.filter((t) => t.status === "active").length;
  const totalSent = executions.filter((e) => e.status === "completed").length;
  const totalReengaged = executions.reduce((acc, e) => acc + e.sent_count, 0);
  const avgOpenRate = 68.4;

  if (session.loading || dataLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  function getTemplateName(templateId: number) {
    return templates.find((t) => t.id === templateId)?.name ?? `Template #${templateId}`;
  }

  async function handleActivate(id: number) {
    try {
      await activateCampaignTemplate(id, csrfToken);
      await fetchData();
    } catch {
      // TODO: toast error
    }
  }

  async function handleSend(templateId: number) {
    try {
      await sendCampaign(templateId, csrfToken);
      await fetchData();
    } catch {
      // TODO: toast error
    }
  }

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-white mb-2">
            Campanhas WhatsApp
          </h1>
          <p className="text-on-surface-variant max-w-xl text-sm">
            Comunicacao e reengajamento. Gerencie modelos de mensagem, automatize disparos e
            acompanhe resultados em tempo real.
          </p>
        </div>
        <Button
          icon="add_circle"
          onClick={() => setShowModal(true)}
          className="rounded-full shadow-lg shadow-primary/20"
        >
          Novo Modelo
        </Button>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="description" label="Modelos Ativos" value={activeTemplates} />
        <StatCard
          icon="send"
          label="Campanhas Enviadas"
          value={totalSent}
          delta={`${totalSent} envios`}
          deltaType="up"
        />
        <StatCard
          icon="visibility"
          label="Taxa de Abertura"
          value={`${avgOpenRate}%`}
          delta="+5.2% vs mes anterior"
          deltaType="up"
        />
        <StatCard
          icon="person_add"
          label="Reengajados"
          value={totalReengaged.toLocaleString("pt-BR")}
        />
      </div>

      {/* tabs */}
      <div className="flex gap-1 glass-panel rounded-lg p-1 w-fit">
        {(["templates", "executions"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-6 py-2.5 rounded-md text-sm font-bold font-headline uppercase tracking-widest transition-colors",
              activeTab === tab
                ? "bg-primary/10 text-primary"
                : "text-stone-400 hover:text-stone-200 hover:bg-white/5",
            )}
          >
            {tab === "templates" ? "Modelos" : "Envios realizados"}
          </button>
        ))}
      </div>

      {/* tab content: templates */}
      {activeTab === "templates" && (
        <div className="space-y-4">
          {templates.length === 0 && (
            <Card padding="sm" className="text-center text-stone-400 py-12">
              <MaterialIcon icon="description" className="text-stone-600 mb-2" />
              <p className="text-sm">Nenhum modelo de campanha encontrado.</p>
              <p className="text-xs text-stone-500 mt-1">
                Crie o primeiro modelo clicando em &quot;Novo Modelo&quot;.
              </p>
            </Card>
          )}
          {templates.map((tpl) => {
            const ch = channelConfig[tpl.channel] ?? channelConfig.whatsapp;
            const st = templateStatusConfig[tpl.status];
            return (
              <Card
                key={tpl.id}
                padding="sm"
                className={cn(
                  "flex flex-col md:flex-row md:items-center gap-4 group hover:border-white/10 transition-all",
                  tpl.status === "active" && "border-l-4 border-l-primary",
                )}
              >
                {/* icon */}
                <div className="p-3 bg-surface-container rounded-lg shrink-0 self-start">
                  <MaterialIcon
                    icon={ch.icon}
                    className={cn(tpl.status === "active" ? "text-primary" : "text-stone-400")}
                  />
                </div>

                {/* info */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <h4 className="font-bold text-sm text-white font-headline truncate">
                      {tpl.name}
                    </h4>
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full uppercase",
                        ch.color,
                      )}
                    >
                      <MaterialIcon icon={ch.icon} size="sm" />
                      {ch.label}
                    </span>
                    <Badge tone={st.tone}>{st.label}</Badge>
                  </div>
                  {tpl.description && (
                    <p className="text-[10px] text-stone-500 mb-2">{tpl.description}</p>
                  )}
                  <p className="text-xs text-stone-400 line-clamp-2">{tpl.template_body}</p>
                </div>

                {/* actions */}
                <div className="flex items-center gap-2 shrink-0 self-start md:self-center">
                  <button className="p-2 rounded-lg hover:bg-white/5 text-stone-500 hover:text-primary transition-colors">
                    <MaterialIcon icon="edit" size="sm" />
                  </button>
                  {tpl.status === "active" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="send"
                      onClick={() => handleSend(tpl.id)}
                    >
                      Enviar
                    </Button>
                  )}
                  {tpl.status === "draft" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="check_circle"
                      onClick={() => handleActivate(tpl.id)}
                    >
                      Ativar
                    </Button>
                  )}
                  <button className="p-2 rounded-lg hover:bg-white/5 text-stone-500 hover:text-stone-200 transition-colors">
                    <MaterialIcon icon="more_vert" size="sm" />
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* tab content: executions */}
      {activeTab === "executions" && (
        <div className="space-y-4">
          {executions.length === 0 && (
            <Card padding="sm" className="text-center text-stone-400 py-12">
              <MaterialIcon icon="send" className="text-stone-600 mb-2" />
              <p className="text-sm">Nenhum envio realizado ainda.</p>
            </Card>
          )}

          {executions.length > 0 && (
            <>
              {/* table for desktop */}
              <Card padding="sm" className="hidden md:block overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Campanha
                        </th>
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Status
                        </th>
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Enviados / Total
                        </th>
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Progresso
                        </th>
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Falhas
                        </th>
                        <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-stone-500">
                          Data
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {executions.map((exec) => {
                        const st = executionStatusConfig[exec.status];
                        const pct =
                          exec.total_patients > 0
                            ? Math.round((exec.sent_count / exec.total_patients) * 100)
                            : 0;
                        const progressVariant =
                          exec.status === "failed"
                            ? "danger"
                            : exec.status === "completed"
                              ? "success"
                              : "primary";
                        return (
                          <tr key={exec.id} className="hover:bg-white/5 transition-colors">
                            <td className="px-5 py-4">
                              <p className="font-bold text-sm text-stone-200 font-headline">
                                {getTemplateName(exec.template_id)}
                              </p>
                            </td>
                            <td className="px-5 py-4">
                              <Badge tone={st.tone} pulse={exec.status === "in_progress"}>
                                {st.label}
                              </Badge>
                            </td>
                            <td className="px-5 py-4 text-sm text-stone-300">
                              {exec.sent_count.toLocaleString("pt-BR")} /{" "}
                              {exec.total_patients.toLocaleString("pt-BR")}
                            </td>
                            <td className="px-5 py-4 w-40">
                              <ProgressBar value={pct} variant={progressVariant} size="sm" />
                            </td>
                            <td className="px-5 py-4 text-sm">
                              {exec.failed_count > 0 ? (
                                <span className="text-error font-bold">{exec.failed_count}</span>
                              ) : (
                                <span className="text-stone-500">0</span>
                              )}
                            </td>
                            <td className="px-5 py-4 text-xs text-stone-400">
                              {fmtDate(exec.started_at)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* cards for mobile */}
              <div className="md:hidden space-y-3">
                {executions.map((exec) => {
                  const st = executionStatusConfig[exec.status];
                  const pct =
                    exec.total_patients > 0
                      ? Math.round((exec.sent_count / exec.total_patients) * 100)
                      : 0;
                  const progressVariant =
                    exec.status === "failed"
                      ? "danger"
                      : exec.status === "completed"
                        ? "success"
                        : "primary";
                  return (
                    <Card key={exec.id} padding="sm">
                      <div className="flex justify-between items-start mb-3">
                        <div>
                          <Badge tone={st.tone} pulse={exec.status === "in_progress"}>
                            {st.label}
                          </Badge>
                          <h4 className="font-bold text-sm text-white font-headline mt-1">
                            {getTemplateName(exec.template_id)}
                          </h4>
                        </div>
                        <span className="text-xs text-stone-400">{fmtDate(exec.started_at)}</span>
                      </div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-stone-500">
                          {exec.sent_count}/{exec.total_patients} enviados
                        </span>
                        {exec.failed_count > 0 && (
                          <span className="text-xs text-error font-bold">
                            {exec.failed_count} falhas
                          </span>
                        )}
                      </div>
                      <ProgressBar value={pct} variant={progressVariant} size="sm" />
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      {/* template preview + trigger logic cards (desktop) */}
      {activeTab === "templates" && templates.some((t) => t.status === "active") && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* template preview */}
          <Card className="border-t-2 border-primary/30">
            <div className="flex items-center justify-between mb-6">
              <h4 className="font-bold font-headline text-stone-200 flex items-center gap-2">
                <MaterialIcon icon="description" className="text-primary" />
                Modelo: Renovacao
              </h4>
              <button className="p-1.5 hover:bg-white/5 rounded-md text-stone-500 hover:text-stone-200 transition-colors">
                <MaterialIcon icon="edit" size="sm" />
              </button>
            </div>
            <div className="bg-stone-950/50 p-4 rounded-xl border border-stone-800/50 mb-4 text-xs leading-relaxed text-stone-300">
              Ola,{" "}
              <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded">
                {"{{patient_name}}"}
              </span>
              !
              <br />
              <br />
              Passando para lembrar que sua receita medica expira em{" "}
              <span className="text-primary font-bold">15 dias</span>.
              <br />
              <br />
              Deseja agendar uma consulta de retorno com o{" "}
              <span className="bg-primary/20 text-primary px-1.5 py-0.5 rounded">
                {"{{doctor_name}}"}
              </span>{" "}
              agora mesmo?
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-stone-500">Campos utilizados: 2/5</span>
              <button className="text-xs text-primary font-bold hover:underline">
                Visualizar mensagem
              </button>
            </div>
          </Card>

          {/* trigger logic */}
          <Card>
            <h4 className="font-bold font-headline text-stone-200 flex items-center gap-2 mb-6">
              <MaterialIcon icon="smart_toy" className="text-primary" />
              Logica de Disparo
            </h4>
            <div className="space-y-4">
              {[
                {
                  step: 1,
                  title: "Evento Detectado",
                  desc: "Receita expirando em < 15 dias.",
                },
                {
                  step: 2,
                  title: "Verificar Horario",
                  desc: "Enviar durante horario comercial (09:00 - 18:00).",
                },
                {
                  step: 3,
                  title: "Disparo",
                  desc: "Enviar via WhatsApp Business API.",
                },
              ].map((item) => (
                <div key={item.step} className="flex items-start gap-4">
                  <div className="mt-1 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-bold text-primary">{item.step}</span>
                  </div>
                  <p className="text-xs text-stone-400">
                    <strong className="text-stone-200 block">{item.title}</strong>
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* CTA banner */}
      <Card className="overflow-hidden relative flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 blur-[100px] rounded-full pointer-events-none" />
        <div className="relative z-10">
          <h2 className="text-2xl font-black font-headline text-white mb-2">
            Automatize seu alcance clinico.
          </h2>
          <p className="text-stone-400 max-w-md text-sm">
            Use segmentacao com IA para alcancar os pacientes certos com lembretes medicos no
            momento ideal.
          </p>
        </div>
        <Button
          className="relative z-10 rounded-xl shadow-2xl shadow-primary/20"
          size="lg"
          onClick={() => setShowModal(true)}
        >
          Iniciar Nova Campanha
        </Button>
      </Card>

      {/* modal */}
      <NewTemplateModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={(t) => {
          setTemplates((prev) => [t, ...prev]);
        }}
        csrfToken={csrfToken}
      />
    </div>
  );
}
