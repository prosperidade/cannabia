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

const OVERALL_SCORE = 87;

type CheckStatus = "conforme" | "pendente" | "vencido";

type CheckItem = {
  label: string;
  status: CheckStatus;
  detail: string;
};

const DOC_CHECKS: CheckItem[] = [
  { label: "CNPJ Ativo", status: "conforme", detail: "Valido ate 2027" },
  { label: "Alvara Sanitario", status: "conforme", detail: "Valido ate 12/2026" },
  { label: "Cadastro CNES", status: "conforme", detail: "Atualizado em 03/2026" },
  { label: "Licenca ANVISA (AFE)", status: "pendente", detail: "Renovacao ate 06/2026" },
  { label: "CRF do Farmaceutico", status: "vencido", detail: "Venceu em 01/2026" },
];

const PRESC_CHECKS: CheckItem[] = [
  { label: "Assinatura Digital ICP-Brasil", status: "conforme", detail: "98.5% das prescricoes" },
  { label: "Formato ANVISA (SNGPC)", status: "conforme", detail: "100% conforme" },
  { label: "Notificacao de Receita B", status: "pendente", detail: "3 pendentes de envio" },
  { label: "Registro de Controle Especial", status: "conforme", detail: "Atualizado" },
];

const RASTREAB_CHECKS: CheckItem[] = [
  { label: "Rastreamento de Lotes", status: "conforme", detail: "Cobertura 96.8%" },
  { label: "Log de Dispensacao", status: "conforme", detail: "Taxa 99.2%" },
  { label: "Controle de Validade", status: "pendente", detail: "12 lotes proximos do vencimento" },
  { label: "Certificado de Analise (COA)", status: "conforme", detail: "Todos os lotes verificados" },
];

const DADOS_CHECKS: CheckItem[] = [
  { label: "Conformidade LGPD", status: "conforme", detail: "DPO nomeado, politicas ativas" },
  { label: "Criptografia de Dados", status: "conforme", detail: "AES-256 em repouso, TLS 1.3" },
  { label: "Backup Automatico", status: "conforme", detail: "Ultimo: ha 2 horas" },
  { label: "Termo de Consentimento", status: "pendente", detail: "4 pacientes sem assinatura" },
];

type AuditEvent = {
  date: string;
  event: string;
  status: "success" | "warning" | "error";
  detail: string;
};

const AUDIT_EVENTS: AuditEvent[] = [
  { date: "07/04/2026 14:22", event: "Verificacao de lote CBD-BR-9921", status: "success", detail: "Lote aprovado no controle de qualidade" },
  { date: "07/04/2026 11:05", event: "Upload SNGPC mensal", status: "success", detail: "Relatorio enviado com sucesso" },
  { date: "06/04/2026 16:45", event: "Alerta de vencimento CRF", status: "error", detail: "Certificado do farmaceutico vencido" },
  { date: "06/04/2026 09:12", event: "Renovacao de licenca", status: "warning", detail: "Licenca AFE proxima do vencimento" },
  { date: "05/04/2026 18:30", event: "Backup automatico concluido", status: "success", detail: "Banco de dados replicado com sucesso" },
  { date: "05/04/2026 10:00", event: "Auditoria interna trimestral", status: "success", detail: "Nenhuma nao-conformidade encontrada" },
  { date: "04/04/2026 14:15", event: "Atualizacao politica LGPD", status: "success", detail: "Novos termos publicados" },
  { date: "03/04/2026 09:45", event: "Evento adverso reportado", status: "warning", detail: "Tontura moderada - Paciente #P-882" },
];

const STATUS_BADGE: Record<CheckStatus, { tone: "primary" | "warning" | "danger"; label: string }> = {
  conforme: { tone: "primary", label: "Conforme" },
  pendente: { tone: "warning", label: "Pendente" },
  vencido: { tone: "danger", label: "Vencido" },
};

const EVENT_STATUS_MAP = {
  success: { tone: "primary" as const, icon: "check_circle" },
  warning: { tone: "warning" as const, icon: "warning" },
  error: { tone: "danger" as const, icon: "error" },
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function CompliancePage() {
  const [expandedSection, setExpandedSection] = useState<string | null>("documentacao");

  const toggleSection = (section: string) => {
    setExpandedSection((prev) => (prev === section ? null : section));
  };

  const totalItems = DOC_CHECKS.length + PRESC_CHECKS.length + RASTREAB_CHECKS.length + DADOS_CHECKS.length;
  const conformeItems = [...DOC_CHECKS, ...PRESC_CHECKS, ...RASTREAB_CHECKS, ...DADOS_CHECKS].filter(
    (c) => c.status === "conforme",
  ).length;
  const pendenteItems = [...DOC_CHECKS, ...PRESC_CHECKS, ...RASTREAB_CHECKS, ...DADOS_CHECKS].filter(
    (c) => c.status === "pendente",
  ).length;
  const vencidoItems = [...DOC_CHECKS, ...PRESC_CHECKS, ...RASTREAB_CHECKS, ...DADOS_CHECKS].filter(
    (c) => c.status === "vencido",
  ).length;

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
          <Button variant="secondary" icon="history" size="sm" onClick={() => alert("Arquivo de periodo (mock)")}>
            Arquivo Periodo
          </Button>
          <Button variant="primary" icon="upload_file" size="sm" onClick={() => alert("Gerar Relatorio ANVISA (mock)")}>
            Gerar Relatorio ANVISA
          </Button>
        </div>
      </div>

      {/* Overview cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard icon="inventory_2" label="Total Lotes Rastreados" value="1.248" delta="+12%" deltaType="up" />
        <StatCard icon="warning" label="Eventos Adversos" value="02" delta="Pendentes" deltaType="down" />
        <StatCard icon="event_repeat" label="Renovacoes Proximas" value="45" delta="< 15 dias" deltaType="neutral" />

        {/* Audit Status Card - special */}
        <Card padding="md" className="border-primary/20 bg-primary/5">
          <div className="flex justify-between items-start mb-3">
            <p className="text-xs font-bold text-primary tracking-wider uppercase">Score Compliance</p>
            <MaterialIcon icon="verified" filled className="text-primary" />
          </div>
          <h3 className="text-3xl font-headline font-extrabold text-on-surface">{OVERALL_SCORE}%</h3>
          <ProgressBar value={OVERALL_SCORE} glow className="mt-3" />
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
                {vencidoItems > 0 && <span className="text-error">{vencidoItems} item(ns) vencido(s) requerem acao imediata.</span>}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Main grid: checklist + events */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Checklist Sections */}
        <div className="xl:col-span-2 space-y-4">
          <ChecklistSection
            title="Documentacao"
            icon="description"
            sectionKey="documentacao"
            items={DOC_CHECKS}
            expanded={expandedSection === "documentacao"}
            onToggle={toggleSection}
          />
          <ChecklistSection
            title="Prescricoes"
            icon="medication"
            sectionKey="prescricoes"
            items={PRESC_CHECKS}
            expanded={expandedSection === "prescricoes"}
            onToggle={toggleSection}
          />
          <ChecklistSection
            title="Rastreabilidade"
            icon="local_shipping"
            sectionKey="rastreabilidade"
            items={RASTREAB_CHECKS}
            expanded={expandedSection === "rastreabilidade"}
            onToggle={toggleSection}
          />
          <ChecklistSection
            title="Dados e LGPD"
            icon="shield"
            sectionKey="dados"
            items={DADOS_CHECKS}
            expanded={expandedSection === "dados"}
            onToggle={toggleSection}
          />
        </div>

        {/* Audit Event Log */}
        <div className="space-y-4">
          <Card padding="md">
            <h4 className="text-lg font-headline font-bold text-on-surface mb-4 flex items-center gap-2">
              <MaterialIcon icon="history" size="sm" className="text-primary" />
              Eventos de Auditoria
            </h4>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {AUDIT_EVENTS.map((evt, idx) => {
                const cfg = EVENT_STATUS_MAP[evt.status];
                return (
                  <div
                    key={idx}
                    className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <MaterialIcon icon={cfg.icon} size="sm" className={cn(
                          cfg.tone === "primary" && "text-primary",
                          cfg.tone === "warning" && "text-amber-400",
                          cfg.tone === "danger" && "text-error",
                        )} />
                        <Badge tone={cfg.tone}>
                          {evt.status === "success" ? "OK" : evt.status === "warning" ? "Alerta" : "Critico"}
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
            <h4 className="text-lg font-headline font-bold text-on-surface mb-4">Eficacia Clinica</h4>
            <div className="space-y-4">
              {[
                { label: "Reducao Media de Dor", value: "64.2%", color: "text-primary" },
                { label: "Duracao Media Tratamento", value: "112 dias", color: "text-on-surface" },
                { label: "Retencao de Pacientes", value: "89%", color: "text-secondary" },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center justify-between">
                  <span className="text-xs text-stone-500 uppercase tracking-widest font-bold">{stat.label}</span>
                  <span className={cn("text-lg font-headline font-extrabold", stat.color)}>{stat.value}</span>
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
            <ProgressBar value={sectionPct} size="sm" variant={sectionPct === 100 ? "success" : sectionPct >= 75 ? "primary" : "warning"} />
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
                <Badge tone={cfg.tone} className="shrink-0">{cfg.label}</Badge>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
