"use client";

/**
 * Admin Sandbox Overview — visao multi-tenant do estado regulatorio.
 * F1.5 (extensao): Admin acompanha todas associacoes cadastradas.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  adminListAssociations,
  type AssociationAdminSummary,
} from "@/lib/governance";
import { Badge, Button, Card, MaterialIcon } from "@/components/ui-tw";

function statusTone(status: string | null): "neutral" | "warning" | "info" | "success" | "danger" {
  if (!status) return "neutral";
  switch (status) {
    case "approved":
    case "active":
      return "success";
    case "submitted":
    case "under_review":
      return "info";
    case "preparing":
      return "warning";
    case "discontinued":
    case "suspended":
      return "danger";
    default:
      return "neutral";
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("pt-BR");
  } catch {
    return iso;
  }
}

function readinessFromSummary(row: AssociationAdminSummary): {
  label: string;
  tone: "success" | "warning" | "danger";
  score: number;
} {
  // Heuristica visual simples: conta quantos dos 4 criterios "duros" ja
  // estao satisfeitos. O check completo vive em /api/v1/governance/eligibility.
  const criteria = [
    row.tenant_type === "association",
    !!row.incorporation_date,
    row.rt_count > 0,
    row.has_capacity,
  ];
  const score = criteria.filter(Boolean).length;
  if (score === 4) return { label: "Pronto", tone: "success", score };
  if (score >= 2) return { label: "Em preparacao", tone: "warning", score };
  return { label: "Inicial", tone: "danger", score };
}

export default function AdminSandboxPage() {
  const [rows, setRows] = useState<AssociationAdminSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { associations } = await adminListAssociations();
      setRows(associations);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Falha ao carregar associacoes.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = {
    all: rows.length,
    ready: rows.filter((r) => readinessFromSummary(r).score === 4).length,
    preparing: rows.filter((r) => r.sandbox_application_status === "preparing").length,
    submitted: rows.filter((r) => r.sandbox_application_status === "submitted").length,
  };

  return (
    <div className="space-y-6 pb-10">
      <header>
        <div className="flex items-center gap-2 mb-2">
          <MaterialIcon icon="account_balance" size="sm" className="text-primary" />
          <span className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
            Plataforma · Sandbox Regulatorio
          </span>
        </div>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-headline font-extrabold text-on-surface">
              Associacoes no Sandbox
            </h1>
            <p className="text-sm text-stone-400 mt-1 max-w-2xl">
              Visao multi-tenant do estado regulatorio (RDC 1.014/2026). Cada
              linha representa uma associacao cadastrada na plataforma.
            </p>
          </div>
          <Button variant="secondary" size="sm" icon="refresh" onClick={load} disabled={loading}>
            Atualizar
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Total" value={totals.all} icon="groups" />
        <StatTile label="Criterios cumpridos" value={totals.ready} icon="check_circle" tone="success" />
        <StatTile label="Em preparacao" value={totals.preparing} icon="edit_note" tone="warning" />
        <StatTile label="Submetidas" value={totals.submitted} icon="send" tone="info" />
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-error/10 border border-error/30 text-sm text-error">
          {error}
        </div>
      )}

      <Card>
        {loading && rows.length === 0 ? (
          <div className="py-12 flex items-center justify-center">
            <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          </div>
        ) : rows.length === 0 ? (
          <div className="py-12 text-center">
            <MaterialIcon icon="inbox" size="md" className="text-stone-500 mb-2" />
            <p className="text-sm text-stone-400">Nenhuma associacao cadastrada ainda.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-widest text-stone-500 border-b border-outline-variant/20">
                  <th className="text-left font-bold py-3 pr-4">Associacao</th>
                  <th className="text-left font-bold py-3 pr-4">Status Sandbox</th>
                  <th className="text-left font-bold py-3 pr-4">Prontidao</th>
                  <th className="text-right font-bold py-3 pr-4">Associados</th>
                  <th className="text-right font-bold py-3 pr-4">RTs</th>
                  <th className="text-center font-bold py-3 pr-4">Capacidade</th>
                  <th className="text-center font-bold py-3 pr-4">Estatuto</th>
                  <th className="text-left font-bold py-3">Validado em</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const readiness = readinessFromSummary(r);
                  return (
                    <tr
                      key={r.tenant_id}
                      className="border-b border-outline-variant/10 hover:bg-surface-container-low/60 transition-colors"
                    >
                      <td className="py-3 pr-4">
                        <div className="text-on-surface font-semibold">{r.legal_name}</div>
                        {r.trade_name && r.trade_name !== r.legal_name && (
                          <div className="text-xs text-stone-500">{r.trade_name}</div>
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        <Badge tone={statusTone(r.sandbox_application_status)}>
                          {r.sandbox_application_status ?? "nao iniciado"}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <Badge tone={readiness.tone}>{readiness.label}</Badge>
                          <span className="text-xs text-stone-500">{readiness.score}/4</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-right text-on-surface">
                        {r.members_count ?? "—"}
                      </td>
                      <td className="py-3 pr-4 text-right text-on-surface">{r.rt_count}</td>
                      <td className="py-3 pr-4 text-center">
                        <MaterialIcon
                          icon={r.has_capacity ? "check_circle" : "cancel"}
                          size="sm"
                          className={r.has_capacity ? "text-emerald-400" : "text-stone-600"}
                        />
                      </td>
                      <td className="py-3 pr-4 text-center">
                        <MaterialIcon
                          icon={r.has_statute ? "check_circle" : "cancel"}
                          size="sm"
                          className={r.has_statute ? "text-emerald-400" : "text-stone-600"}
                        />
                      </td>
                      <td className="py-3 text-stone-400 text-xs">
                        {formatDate(r.eligibility_validated_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="text-xs text-stone-500">
        Este dashboard agrega sinais rapidos do banco. Para o relatorio completo
        de elegibilidade de uma associacao especifica, use o acesso do atendente
        dela em <code className="text-primary">/org/sandbox/governance</code>.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  StatTile                                                           */
/* ------------------------------------------------------------------ */

function StatTile({
  label,
  value,
  icon,
  tone = "primary",
}: {
  label: string;
  value: number;
  icon: string;
  tone?: "primary" | "success" | "warning" | "info";
}) {
  const toneClass = {
    primary: "text-primary",
    success: "text-emerald-400",
    warning: "text-amber-400",
    info: "text-blue-400",
  }[tone];

  return (
    <div className="p-4 rounded-lg bg-surface-container-low border border-outline-variant/20">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
          {label}
        </span>
        <MaterialIcon icon={icon} size="sm" className={toneClass} />
      </div>
      <div className="text-2xl font-headline font-extrabold text-on-surface">
        {value}
      </div>
    </div>
  );
}
