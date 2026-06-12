"use client";

import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/cn";
import { getOrgCompliance } from "@/lib/api";
import { Card, StatCard, Button, Badge, MaterialIcon, ProgressBar } from "@/components/ui-tw";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

type CheckStatus = "conforme" | "pendente" | "vencido";

type CheckItem = {
  label: string;
  status: CheckStatus;
  detail: string;
  category?: string;
};

type AuditEvent = {
  date: string;
  event: string;
  status: "success" | "warning" | "error";
  detail: string;
};

const STATUS_BADGE: Record<CheckStatus, { tone: "primary" | "warning" | "danger"; label: string }> =
  {
    conforme: { tone: "primary", label: "Conforme" },
    pendente: { tone: "warning", label: "Pendente" },
    vencido: { tone: "danger", label: "Vencido" },
  };

const EVENT_STATUS_MAP = {
  success: { tone: "primary" as const, icon: "check_circle" },
  warning: { tone: "warning" as const, icon: "warning" },
  error: { tone: "danger" as const, icon: "error" },
};

const SECTION_META: Record<string, { title: string; icon: string }> = {
  documentacao: { title: "Documentacao", icon: "description" },
  prescricoes: { title: "Prescricoes", icon: "medication" },
  rastreabilidade: { title: "Rastreabilidade", icon: "local_shipping" },
  dados: { title: "Dados e LGPD", icon: "shield" },
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function CompliancePage() {
  const [expandedSection, setExpandedSection] = useState<string | null>("documentacao");
  const [loading, setLoading] = useState(true);

  const [overallScore, setOverallScore] = useState(0);
  const [checks, setChecks] = useState<CheckItem[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);

  const toggleSection = (section: string) => {
    setExpandedSection((prev) => (prev === section ? null : section));
  };

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getOrgCompliance();
      const d = res.data as Record<string, unknown>;

      if (typeof d.score === "number") setOverallScore(d.score);
      if (Array.isArray(d.checks)) setChecks(d.checks as CheckItem[]);
      if (Array.isArray(d.audit_events)) setAuditEvents(d.audit_events as AuditEvent[]);
    } catch {
      // keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Group checks by category
  const grouped = checks.reduce<Record<string, CheckItem[]>>((acc, item) => {
    const cat = item.category ?? "documentacao";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  const totalItems = checks.length;
  const conformeItems = checks.filter((c) => c.status === "conforme").length;
  const pendenteItems = checks.filter((c) => c.status === "pendente").length;
  const vencidoItems = checks.filter((c) => c.status === "vencido").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <MaterialIcon icon="hourglass_empty" size="xl" className="text-primary animate-spin" />
          <p className="text-stone-400 text-sm">Carregando compliance...</p>
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
            Relatorios e Compliance ANVISA
          </h2>
          <p className="text-stone-400 text-sm mt-1 italic">
            Centro de Auditoria Digital - Conformidade regulatoria em tempo real
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Button
            variant="secondary"
            icon="history"
            size="sm"
            onClick={() => alert("Arquivo de periodo")}
          >
            Arquivo Periodo
          </Button>
          <Button
            variant="primary"
            icon="upload_file"
            size="sm"
            onClick={() => alert("Gerar Relatorio ANVISA")}
          >
            Gerar Relatorio ANVISA
          </Button>
        </div>
      </div>

      {/* Overview cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          icon="inventory_2"
          label="Total Lotes Rastreados"
          value="1.248"
          delta="+12%"
          deltaType="up"
        />
        <StatCard
          icon="warning"
          label="Eventos Adversos"
          value="02"
          delta="Pendentes"
          deltaType="down"
        />
        <StatCard
          icon="event_repeat"
          label="Renovacoes Proximas"
          value="45"
          delta="< 15 dias"
          deltaType="neutral"
        />

        {/* Audit Status Card - special */}
        <Card padding="md" className="border-primary/20 bg-primary/5">
          <div className="flex justify-between items-start mb-3">
            <p className="text-xs font-bold text-primary tracking-wider uppercase">
              Score Compliance
            </p>
            <MaterialIcon icon="verified" filled className="text-primary" />
          </div>
          <h3 className="text-3xl font-headline font-extrabold text-on-surface">{overallScore}%</h3>
          <ProgressBar value={overallScore} glow className="mt-3" />
          <p className="text-[11px] text-stone-400 mt-2">
            {conformeItems}/{totalItems} itens conformes
          </p>
        </Card>
      </div>

      {/* Alerts for items needing attention */}
      {(pendenteItems > 0 || vencidoItems > 0) && (
        <Card padding="md" className="border-l-4 border-amber-500/50 bg-amber-500/5">
          <div className="flex items-start gap-3">
            <MaterialIcon icon="notification_important" className="text-amber-400 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-on-surface">Atencao Necessaria</p>
              <p className="text-xs text-stone-400 mt-1">
                {pendenteItems > 0 && <span>{pendenteItems} item(ns) pendente(s). </span>}
                {vencidoItems > 0 && (
                  <span className="text-error">
                    {vencidoItems} item(ns) vencido(s) requerem acao imediata.
                  </span>
                )}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Main grid: checklist + events */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Checklist Sections */}
        <div className="xl:col-span-2 space-y-4">
          {Object.entries(grouped).map(([sectionKey, items]) => {
            const meta = SECTION_META[sectionKey] ?? { title: sectionKey, icon: "checklist" };
            return (
              <ChecklistSection
                key={sectionKey}
                title={meta.title}
                icon={meta.icon}
                sectionKey={sectionKey}
                items={items}
                expanded={expandedSection === sectionKey}
                onToggle={toggleSection}
              />
            );
          })}
        </div>

        {/* Audit Event Log */}
        <div className="space-y-4">
          <Card padding="md">
            <h4 className="text-lg font-headline font-bold text-on-surface mb-4 flex items-center gap-2">
              <MaterialIcon icon="history" size="sm" className="text-primary" />
              Eventos de Auditoria
            </h4>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {auditEvents.map((evt, idx) => {
                const cfg = EVENT_STATUS_MAP[evt.status];
                return (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <MaterialIcon
                          icon={cfg.icon}
                          size="sm"
                          className={cn(
                            cfg.tone === "primary" && "text-primary",
                            cfg.tone === "warning" && "text-amber-400",
                            cfg.tone === "danger" && "text-error",
                          )}
                        />
                        <Badge tone={cfg.tone}>
                          {evt.status === "success"
                            ? "OK"
                            : evt.status === "warning"
                              ? "Alerta"
                              : "Critico"}
                        </Badge>
                      </div>
                      <span className="text-[10px] text-stone-500 font-mono">{evt.date}</span>
                    </div>
                    <p className="text-sm font-semibold text-on-surface">{evt.event}</p>
                    <p className="text-xs text-stone-500">{evt.detail}</p>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Clinical Evolution Stats */}
          <Card padding="md">
            <h4 className="text-lg font-headline font-bold text-on-surface mb-4">
              Eficacia Clinica
            </h4>
            <div className="space-y-4">
              {[
                { label: "Reducao Media de Dor", value: "--", color: "text-primary" },
                { label: "Duracao Media Tratamento", value: "--", color: "text-on-surface" },
                { label: "Retencao de Pacientes", value: "--", color: "text-secondary" },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center justify-between">
                  <span className="text-xs text-stone-500 uppercase tracking-widest font-bold">
                    {stat.label}
                  </span>
                  <span className={cn("text-lg font-headline font-extrabold", stat.color)}>
                    {stat.value}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function ChecklistSection({
  title,
  icon,
  sectionKey,
  items,
  expanded,
  onToggle,
}: {
  title: string;
  icon: string;
  sectionKey: string;
  items: CheckItem[];
  expanded: boolean;
  onToggle: (key: string) => void;
}) {
  const conformeCount = items.filter((i) => i.status === "conforme").length;
  const sectionPct = Math.round((conformeCount / items.length) * 100);

  return (
    <Card padding="sm" className="overflow-hidden">
      <button
        onClick={() => onToggle(sectionKey)}
        className="w-full flex items-center justify-between p-2 hover:bg-white/5 rounded-xl transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-lg">
            <MaterialIcon icon={icon} className="text-primary" size="sm" />
          </div>
          <div className="text-left">
            <h4 className="font-headline font-bold text-on-surface">{title}</h4>
            <p className="text-xs text-stone-500">
              {conformeCount}/{items.length} conformes
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 w-32">
            <ProgressBar
              value={sectionPct}
              size="sm"
              variant={sectionPct === 100 ? "success" : sectionPct >= 75 ? "primary" : "warning"}
            />
            <span className="text-xs font-bold text-stone-400">{sectionPct}%</span>
          </div>
          <MaterialIcon
            icon={expanded ? "expand_less" : "expand_more"}
            className="text-stone-500"
          />
        </div>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 px-2 pb-2">
          {items.map((item) => {
            const cfg = STATUS_BADGE[item.status];
            return (
              <div
                key={item.label}
                className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5"
              >
                <MaterialIcon
                  icon={
                    item.status === "conforme"
                      ? "check_circle"
                      : item.status === "pendente"
                        ? "pending"
                        : "cancel"
                  }
                  filled
                  size="sm"
                  className={cn(
                    item.status === "conforme" && "text-primary",
                    item.status === "pendente" && "text-amber-400",
                    item.status === "vencido" && "text-error",
                  )}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-on-surface">{item.label}</p>
                  <p className="text-xs text-stone-500 truncate">{item.detail}</p>
                </div>
                <Badge tone={cfg.tone} className="shrink-0">
                  {cfg.label}
                </Badge>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
