"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/cn";
import { listTenants } from "@/lib/api";
import {
  StatCard,
  Badge,
  Card,
  Button,
  MaterialIcon,
  SearchBar,
  DataTable,
  ProgressBar,
  Input,
  type DataTableColumn,
} from "@/components/ui-tw";
import type { Tenant, TenantStatus, TenantPlan } from "@/lib/types-admin";

/* ── Data is now loaded from API ── */

/* ── Helpers ── */

const statusTone: Record<TenantStatus, "success" | "warning" | "danger" | "neutral"> = {
  active: "success",
  trial: "info" as "warning",
  suspended: "danger",
  cancelled: "neutral",
};

const statusLabel: Record<TenantStatus, string> = {
  active: "Ativo",
  trial: "Avaliacao",
  suspended: "Suspenso",
  cancelled: "Cancelado",
};

const planLabel: Record<TenantPlan, string> = {
  starter: "Starter",
  professional: "Professional",
  enterprise: "Enterprise",
};

const planTone: Record<TenantPlan, "primary" | "info" | "warning"> = {
  starter: "primary",
  professional: "info" as "primary",
  enterprise: "warning",
};

const typeMap: Record<string, { label: string; tone: "primary" | "success" | "info" }> = {
  clinic: { label: "Clinica", tone: "primary" },
  association: { label: "Associacao", tone: "success" },
  doctor: { label: "Medico", tone: "info" },
};

function inferType(t: Tenant): string {
  if (t.name.startsWith("Dr.") || t.name.startsWith("Dra.")) return "doctor";
  if (t.name.toLowerCase().includes("assoc") || t.name.toLowerCase().includes("instituto"))
    return "association";
  return "clinic";
}

function usagePct(used: number, limit: number) {
  if (limit === 0) return 0;
  return Math.round((used / limit) * 100);
}

type StatusFilter = "all" | TenantStatus;
type PlanFilter = "all" | TenantPlan;

/* ── Page ── */

export default function TenantsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [planFilter, setPlanFilter] = useState<PlanFilter>("all");
  const [showNewModal, setShowNewModal] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  /* New tenant form state */
  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formType, setFormType] = useState("clinic");
  const [formPlan, setFormPlan] = useState<TenantPlan>("starter");

  useEffect(() => {
    let cancelled = false;
    async function fetchTenants() {
      try {
        setApiLoading(true);
        setApiError(null);
        const data = await listTenants();
        if (cancelled) return;
        setTenants(data);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar os tenants.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchTenants();
    return () => { cancelled = true; };
  }, []);

  const filtered = tenants.filter((t) => {
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (planFilter !== "all" && t.plan !== planFilter) return false;
    if (
      search &&
      !t.name.toLowerCase().includes(search.toLowerCase()) &&
      !t.slug.toLowerCase().includes(search.toLowerCase())
    )
      return false;
    return true;
  });

  const totalCount = tenants.length;
  const activeCount = tenants.filter((t) => t.status === "active").length;
  const trialCount = tenants.filter((t) => t.status === "trial").length;
  const suspendedCount = tenants.filter((t) => t.status === "suspended").length;

  const statusFilters: { value: StatusFilter; label: string }[] = [
    { value: "all", label: "Todos" },
    { value: "active", label: "Ativos" },
    { value: "trial", label: "Avaliacao" },
    { value: "suspended", label: "Suspensos" },
    { value: "cancelled", label: "Cancelados" },
  ];

  const planFilters: { value: PlanFilter; label: string }[] = [
    { value: "all", label: "Todos planos" },
    { value: "starter", label: "Starter" },
    { value: "professional", label: "Professional" },
    { value: "enterprise", label: "Enterprise" },
  ];

  const columns: DataTableColumn[] = [
    {
      key: "name",
      label: "Organizacao",
      sortable: true,
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        const type = inferType(tenant);
        const typeInfo = typeMap[type] ?? typeMap.clinic;
        return (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center border border-primary/20 flex-shrink-0">
              <span className="text-primary font-bold text-xs">
                {tenant.name
                  .split(" ")
                  .map((w) => w[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </span>
            </div>
            <div className="min-w-0">
              <div className="font-bold text-sm text-on-surface truncate">{tenant.name}</div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[10px] font-mono text-stone-500">{tenant.slug}</span>
                <Badge tone={typeInfo.tone as "primary"} className="!text-[8px] !px-1.5">
                  {typeInfo.label}
                </Badge>
              </div>
            </div>
          </div>
        );
      },
    },
    {
      key: "status",
      label: "Status",
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        return (
          <Badge tone={statusTone[tenant.status]} pulse={tenant.status === "trial"}>
            {statusLabel[tenant.status]}
          </Badge>
        );
      },
    },
    {
      key: "plan",
      label: "Plano",
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        return (
          <Badge tone={planTone[tenant.plan] as "primary"}>
            {planLabel[tenant.plan]}
          </Badge>
        );
      },
    },
    {
      key: "clinic_count",
      label: "Clinicas",
      sortable: true,
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        return <span className="text-sm font-bold">{tenant.clinic_count}</span>;
      },
    },
    {
      key: "user_count",
      label: "Usuarios",
      sortable: true,
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        return <span className="text-sm font-bold">{tenant.user_count}</span>;
      },
    },
    {
      key: "ai_executions_month",
      label: "Uso IA",
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        const pct = usagePct(tenant.ai_executions_month, tenant.ai_limit_month);
        return (
          <div className="w-36 space-y-1">
            <div className="flex justify-between text-[10px] font-bold">
              <span>
                {tenant.ai_executions_month.toLocaleString("pt-BR")} /{" "}
                {tenant.ai_limit_month.toLocaleString("pt-BR")}
              </span>
              <span
                className={cn(
                  pct > 90 ? "text-error" : pct > 70 ? "text-amber-400" : "text-primary",
                )}
              >
                {pct}%
              </span>
            </div>
            <ProgressBar
              value={pct}
              size="sm"
              variant={pct > 90 ? "danger" : pct > 70 ? "warning" : "primary"}
            />
          </div>
        );
      },
    },
    {
      key: "created_at",
      label: "Criado em",
      sortable: true,
      render: (_val, row) => {
        const tenant = row as unknown as Tenant;
        return (
          <span className="text-xs text-stone-400">
            {new Date(tenant.created_at).toLocaleDateString("pt-BR")}
          </span>
        );
      },
    },
    {
      key: "actions",
      label: "Acoes",
      render: () => {
        return (
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="sm">
              Detalhes
            </Button>
            <Button variant="ghost" size="sm">
              Editar
            </Button>
          </div>
        );
      },
    },
  ];

  const tableData = filtered.map((t) => ({ ...t } as unknown as Record<string, unknown>));

  if (apiLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando organizacoes...</p>
        </div>
      </div>
    );
  }

  if (apiError && tenants.length === 0) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
          <p className="text-on-surface-variant text-sm">{apiError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* ── Header ── */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <nav className="flex items-center gap-2 text-xs text-stone-500 mb-3">
            <span>Painel Administrativo</span>
            <MaterialIcon icon="chevron_right" size="sm" />
            <span className="text-primary font-semibold">Gestao de Organizacoes</span>
          </nav>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tight text-on-surface">
            Gestao de Organizacoes
          </h1>
          <p className="text-on-surface-variant mt-1 text-sm max-w-lg">
            Administracao de organizacoes clinicas, monitoramento e configuracao.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" icon="download">
            Relatorio
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon="add"
            onClick={() => setShowNewModal(true)}
          >
            Nova Organizacao
          </Button>
        </div>
      </header>

      {/* ── Stats ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon="apartment" label="Total Organizacoes" value={totalCount} />
        <StatCard icon="check_circle" label="Ativos" value={activeCount} />
        <StatCard
          icon="hourglass_top"
          label="Em Avaliacao"
          value={trialCount}
          delta={trialCount > 0 ? `${trialCount} ativo(s)` : undefined}
          deltaType="neutral"
        />
        <StatCard icon="block" label="Suspensos" value={suspendedCount} />
      </div>

      {/* ── Filters ── */}
      <div className="flex flex-col lg:flex-row gap-4">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Filtrar por nome ou identificador..."
          className="lg:w-80"
        />
        <div className="flex flex-wrap items-center gap-2">
          {statusFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={cn(
                "px-4 py-2 rounded-full text-xs font-bold uppercase tracking-widest transition-all active:scale-95",
                statusFilter === f.value
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "bg-white/5 text-stone-400 border border-white/10 hover:border-stone-600",
              )}
            >
              {f.label}
            </button>
          ))}
          <div className="h-6 w-px bg-white/10 mx-1 hidden lg:block" />
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value as PlanFilter)}
            className="bg-surface-container-high border border-outline-variant/30 rounded-xl py-2 px-4 text-xs text-on-surface focus:ring-primary font-bold uppercase tracking-widest"
          >
            {planFilters.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* ── Table ── */}
      <DataTable
        columns={columns}
        data={tableData}
        emptyMessage="Nenhuma organizacao encontrada com os filtros aplicados."
      />

      {/* ── Pagination stub ── */}
      <div className="glass-panel rounded-xl px-6 py-3 flex items-center justify-between">
        <span className="text-xs text-stone-500">
          Exibindo <span className="text-on-surface font-bold">{filtered.length}</span> de{" "}
          <span className="text-on-surface font-bold">{totalCount}</span> organizacoes
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled
            className="p-2 rounded-lg border border-white/10 text-stone-500 disabled:opacity-30"
          >
            <MaterialIcon icon="chevron_left" size="sm" />
          </button>
          <button className="px-3 py-1 rounded-lg bg-primary text-on-primary text-xs font-bold">
            1
          </button>
          <button className="p-2 rounded-lg border border-white/10 text-stone-500 hover:bg-white/5 transition-colors">
            <MaterialIcon icon="chevron_right" size="sm" />
          </button>
        </div>
      </div>

      {/* ── Real-time Monitoring Card ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card variant="glass" padding="md" className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
            <MaterialIcon icon="people" className="text-primary text-2xl" />
          </div>
          <div>
            <p className="text-xs text-stone-500 font-medium uppercase tracking-widest">
              Usuarios Conectados
            </p>
            <p className="text-2xl font-black text-on-surface font-headline">142</p>
          </div>
        </Card>
        <Card variant="glass" padding="md" className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-secondary/10 flex items-center justify-center">
            <MaterialIcon icon="speed" className="text-secondary text-2xl" />
          </div>
          <div>
            <p className="text-xs text-stone-500 font-medium uppercase tracking-widest">
              Requisicoes por Minuto
            </p>
            <p className="text-2xl font-black text-on-surface font-headline">
              2.4k <span className="text-sm font-normal text-stone-500">req/min</span>
            </p>
          </div>
        </Card>
        <Card variant="glass" padding="md" className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-error/10 flex items-center justify-center">
            <MaterialIcon icon="error_outline" className="text-error text-2xl" />
          </div>
          <div>
            <p className="text-xs text-stone-500 font-medium uppercase tracking-widest">
              Taxa de Falhas
            </p>
            <p className="text-2xl font-black text-on-surface font-headline">
              0.12<span className="text-sm font-normal text-stone-500">%</span>
            </p>
          </div>
        </Card>
      </div>

      {/* ── New Tenant Modal ── */}
      {showNewModal && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setShowNewModal(false)}
        >
          <div
            className="glass-panel rounded-2xl p-8 w-full max-w-md space-y-6 animate-in fade-in zoom-in-95"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold font-headline text-on-surface">Nova Organizacao</h2>
              <button
                onClick={() => setShowNewModal(false)}
                className="p-2 text-stone-400 hover:text-on-surface hover:bg-white/5 rounded-lg transition-colors"
              >
                <MaterialIcon icon="close" />
              </button>
            </div>

            <div className="space-y-4">
              <Input
                label="Nome da Organizacao"
                placeholder="Ex: Clinica Verde Vida"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
              />
              <Input
                label="Identificador (URL)"
                placeholder="Ex: verde-vida"
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                hint="Identificador unico. Usado no endereco web."
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  Tipo
                </label>
                <select
                  value={formType}
                  onChange={(e) => setFormType(e.target.value)}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                >
                  <option value="clinic">Clinica</option>
                  <option value="association">Associacao</option>
                  <option value="doctor">Medico Individual</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
                  Plano
                </label>
                <select
                  value={formPlan}
                  onChange={(e) => setFormPlan(e.target.value as TenantPlan)}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
                >
                  <option value="starter">Starter</option>
                  <option value="professional">Professional</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                variant="ghost"
                size="md"
                className="flex-1"
                onClick={() => setShowNewModal(false)}
              >
                Cancelar
              </Button>
              <Button
                variant="primary"
                size="md"
                icon="add"
                className="flex-1"
                onClick={() => {
                  // TODO: call createTenant API
                  setShowNewModal(false);
                }}
              >
                Criar Organizacao
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
