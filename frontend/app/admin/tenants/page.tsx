"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHeadCell,
  TableCell,
  TableEmpty,
} from "@/components/ui/table";
import { TableSkeleton } from "@/components/ui/skeleton";
import type { Tenant, TenantStatus, TenantPlan } from "@/lib/types-admin";

/* ─── Mock data (será substituído por API real na Fase 5.2) ──────── */

const MOCK_TENANTS: Tenant[] = [
  {
    id: 1,
    name: "Clínica Verde Vida",
    slug: "verde-vida",
    status: "active",
    plan: "professional",
    clinic_count: 3,
    user_count: 12,
    ai_executions_month: 847,
    ai_limit_month: 2000,
    created_at: "2025-09-15T10:00:00Z",
    trial_ends_at: null,
  },
  {
    id: 2,
    name: "Instituto Cannábico SP",
    slug: "inst-cannabico-sp",
    status: "active",
    plan: "enterprise",
    clinic_count: 7,
    user_count: 34,
    ai_executions_month: 2341,
    ai_limit_month: 10000,
    created_at: "2025-06-01T10:00:00Z",
    trial_ends_at: null,
  },
  {
    id: 3,
    name: "Dr. Marcos Oliveira",
    slug: "dr-marcos",
    status: "trial",
    plan: "starter",
    clinic_count: 1,
    user_count: 2,
    ai_executions_month: 23,
    ai_limit_month: 100,
    created_at: "2026-03-20T10:00:00Z",
    trial_ends_at: "2026-04-20T10:00:00Z",
  },
  {
    id: 4,
    name: "Rede Cura Natural",
    slug: "cura-natural",
    status: "suspended",
    plan: "professional",
    clinic_count: 2,
    user_count: 8,
    ai_executions_month: 0,
    ai_limit_month: 2000,
    created_at: "2025-11-10T10:00:00Z",
    trial_ends_at: null,
  },
];

/* ─── Helpers ────────────────────────────────────────────────────── */

const statusTone: Record<TenantStatus, "success" | "warning" | "danger" | "neutral"> = {
  active: "success",
  trial: "info" as "warning",
  suspended: "danger",
  cancelled: "neutral",
};

const statusLabel: Record<TenantStatus, string> = {
  active: "Ativo",
  trial: "Trial",
  suspended: "Suspenso",
  cancelled: "Cancelado",
};

const planLabel: Record<TenantPlan, string> = {
  starter: "Starter",
  professional: "Professional",
  enterprise: "Enterprise",
};

function usagePct(used: number, limit: number) {
  if (limit === 0) return 0;
  return Math.round((used / limit) * 100);
}

/* ─── Page ───────────────────────────────────────────────────────── */

export default function TenantsPage() {
  const [search, setSearch] = useState("");
  const [loading] = useState(false);

  const filtered = MOCK_TENANTS.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.slug.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <>
      <header className="workspace-header">
        <div>
          <p className="eyebrow">Administração</p>
          <h1>Tenants</h1>
          <p className="lead">
            Gerencie organizações, planos e limites de uso da plataforma.
          </p>
        </div>
        <Button variant="primary" size="sm">
          + Novo Tenant
        </Button>
      </header>

      {/* Filters */}
      <div style={{ marginBottom: "20px", maxWidth: "400px" }}>
        <Input
          label="Buscar tenant"
          placeholder="Nome ou slug..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Stats */}
      <section aria-label="Resumo de tenants" className="ds-stat-row">
        <div className="ds-stat">
          <span className="ds-stat__label">Total</span>
          <span className="ds-stat__value">{MOCK_TENANTS.length}</span>
        </div>
        <div className="ds-stat">
          <span className="ds-stat__label">Ativos</span>
          <span className="ds-stat__value">
            {MOCK_TENANTS.filter((t) => t.status === "active").length}
          </span>
        </div>
        <div className="ds-stat">
          <span className="ds-stat__label">Em trial</span>
          <span className="ds-stat__value">
            {MOCK_TENANTS.filter((t) => t.status === "trial").length}
          </span>
        </div>
        <div className="ds-stat">
          <span className="ds-stat__label">Suspensos</span>
          <span className="ds-stat__value">
            {MOCK_TENANTS.filter((t) => t.status === "suspended").length}
          </span>
        </div>
      </section>

      {/* Table */}
      <Card padding="sm">
        <CardHeader title="Todos os tenants" />

        {loading ? (
          <TableSkeleton rows={4} cols={6} />
        ) : (
          <Table aria-label="Lista de tenants">
            <TableHeader>
              <TableRow>
                <TableHeadCell>Organização</TableHeadCell>
                <TableHeadCell>Status</TableHeadCell>
                <TableHeadCell>Plano</TableHeadCell>
                <TableHeadCell>Clínicas</TableHeadCell>
                <TableHeadCell>Usuários</TableHeadCell>
                <TableHeadCell>Uso IA</TableHeadCell>
                <TableHeadCell>Ações</TableHeadCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableEmpty colSpan={7} message="Nenhum tenant encontrado." />
              ) : (
                filtered.map((tenant) => {
                  const pct = usagePct(tenant.ai_executions_month, tenant.ai_limit_month);
                  return (
                    <TableRow key={tenant.id}>
                      <TableCell>
                        <div>
                          <strong style={{ display: "block", fontSize: "14px" }}>
                            {tenant.name}
                          </strong>
                          <span className="mono" style={{ fontSize: "12px", color: "var(--muted)" }}>
                            {tenant.slug}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          pulse={tenant.status === "trial"}
                          tone={statusTone[tenant.status]}
                        >
                          {statusLabel[tenant.status]}
                        </Badge>
                      </TableCell>
                      <TableCell>{planLabel[tenant.plan]}</TableCell>
                      <TableCell>{tenant.clinic_count}</TableCell>
                      <TableCell>{tenant.user_count}</TableCell>
                      <TableCell>
                        <div style={{ display: "grid", gap: "4px" }}>
                          <span style={{ fontSize: "13px" }}>
                            {tenant.ai_executions_month.toLocaleString("pt-BR")} /{" "}
                            {tenant.ai_limit_month.toLocaleString("pt-BR")}
                          </span>
                          <div className="bar-meter" style={{ height: "6px" }}>
                            <div
                              className="bar-fill"
                              style={{
                                width: `${Math.min(pct, 100)}%`,
                                background:
                                  pct > 90
                                    ? "var(--rose)"
                                    : pct > 70
                                      ? "var(--amber)"
                                      : undefined,
                              }}
                            />
                          </div>
                          <span style={{ fontSize: "11px", color: "var(--muted)" }}>{pct}%</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button size="sm" variant="ghost">
                          Detalhes
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        )}
      </Card>
    </>
  );
}
