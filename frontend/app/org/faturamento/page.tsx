"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getOrgBilling } from "@/lib/api";
import type { BillingStatus } from "@/lib/types-org";
import {
  Card,
  Badge,
  Button,
  StatCard,
  MaterialIcon,
  ProgressBar,
  DataTable,
  type DataTableColumn,
} from "@/components/ui-tw";

/* ── Types ────────────────────────────────────────────────────────── */

type BillingRecord = {
  id: number;
  patient: string;
  invoiceId: string;
  period: string;
  amount: number;
  dueDate: string;
  status: BillingStatus;
  paidAt: string | null;
};

type DelinquencyAlert = {
  patient: string;
  daysLate: number;
  amount: number;
  invoiceId: string;
};

type CashFlowMonth = {
  label: string;
  entrada: number;
  projecao: number;
};

type BillingData = {
  records: BillingRecord[];
  delinquencyAlerts: DelinquencyAlert[];
  cashFlowMonths: CashFlowMonth[];
  kpi: {
    faturamentoMensal: string;
    aReceber: string;
    inadimplencia: string;
    taxaPagamento: string;
  };
};

type FilterStatus = "todos" | BillingStatus;

const statusBadge: Record<BillingStatus, { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }> = {
  paid: { tone: "success", label: "Pago" },
  pending: { tone: "primary", label: "Pendente" },
  overdue: { tone: "danger", label: "Atrasado" },
  cancelled: { tone: "neutral", label: "Cancelado" },
};

/* ── Page Component ────────────────────────────────────────────────── */

export default function FaturamentoPage() {
  const { data: session } = useApiSession();
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("todos");
  const [filterPeriod, setFilterPeriod] = useState("2026-04");
  const [billingData, setBillingData] = useState<BillingData | null>(null);
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchBilling() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await getOrgBilling();
        if (cancelled) return;
        setBillingData(res.data as unknown as BillingData);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar o faturamento.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchBilling();
    return () => { cancelled = true; };
  }, []);

  const billingRecords = billingData?.records ?? [];
  const delinquencyAlerts = billingData?.delinquencyAlerts ?? [];
  const cashFlowMonths = billingData?.cashFlowMonths ?? [];
  const kpi = billingData?.kpi;

  const filtered = billingRecords.filter((r) =>
    filterStatus === "todos" ? true : r.status === filterStatus,
  );

  const formatCurrency = (v: number) =>
    v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

  const columns: DataTableColumn[] = [
    {
      key: "patient",
      label: "Paciente / ID",
      sortable: true,
      render: (_val, row) => (
        <div>
          <div className="text-sm font-semibold text-on-surface">
            {row.patient as string}
          </div>
          <div className="text-[10px] text-stone-500">{row.invoiceId as string}</div>
        </div>
      ),
    },
    {
      key: "period",
      label: "Periodo",
      sortable: true,
    },
    {
      key: "amount",
      label: "Valor",
      sortable: true,
      render: (val) => (
        <span className="font-bold">{formatCurrency(val as number)}</span>
      ),
    },
    {
      key: "dueDate",
      label: "Vencimento",
      sortable: true,
      render: (val, row) => (
        <span className={cn(row.status === "overdue" && "text-error font-medium")}>
          {new Date(val as string).toLocaleDateString("pt-BR")}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status",
      render: (val) => {
        const s = statusBadge[val as BillingStatus];
        return <Badge tone={s.tone}>{s.label}</Badge>;
      },
    },
    {
      key: "paidAt",
      label: "Pagamento",
      render: (val) =>
        val ? new Date(val as string).toLocaleDateString("pt-BR") : <span className="text-stone-600">--</span>,
    },
    {
      key: "id",
      label: "Acoes",
      render: (_val, row) => (
        <div className="flex items-center gap-2">
          <button className="p-1.5 text-stone-400 hover:text-primary transition-colors rounded-lg hover:bg-white/5">
            <MaterialIcon icon="visibility" size="sm" />
          </button>
          {row.status === "overdue" && (
            <button className="px-3 py-1 bg-error/20 text-error rounded-lg text-xs font-bold hover:bg-error/30 transition-colors">
              Cobrar
            </button>
          )}
          {row.status === "pending" && (
            <button className="p-1.5 text-stone-400 hover:text-primary transition-colors rounded-lg hover:bg-white/5">
              <MaterialIcon icon="notification_add" size="sm" />
            </button>
          )}
        </div>
      ),
    },
  ];

  const tableData = filtered.map((r) => ({
    ...r,
    id: r.id,
    patient: r.patient,
    invoiceId: r.invoiceId,
    period: r.period,
    amount: r.amount,
    dueDate: r.dueDate,
    status: r.status,
    paidAt: r.paidAt,
  }));

  const filterButtons: { label: string; value: FilterStatus }[] = [
    { label: "Todas", value: "todos" },
    { label: "Pagas", value: "paid" },
    { label: "Pendentes", value: "pending" },
    { label: "Atrasadas", value: "overdue" },
    { label: "Canceladas", value: "cancelled" },
  ];

  if (apiLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando faturamento...</p>
        </div>
      </div>
    );
  }

  if (apiError && !billingData) {
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
    <div className="space-y-8">
      {/* Header */}
      <header>
        <h1 className="text-3xl md:text-4xl font-headline font-extrabold tracking-tight text-on-surface">
          Gestao de Faturamento
        </h1>
        <p className="text-on-surface/60 mt-1 text-sm md:text-base">e Inadimplencia</p>
      </header>

      {/* Critical Alert */}
      <section className="glass-panel rounded-2xl p-5 border border-error/20 bg-gradient-to-r from-error/5 to-transparent relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-10">
          <MaterialIcon icon="warning" size="xl" />
        </div>
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-error/20 flex items-center justify-center flex-shrink-0">
              <MaterialIcon icon="warning" filled className="text-error" />
            </div>
            <div>
              <h3 className="text-on-surface font-semibold font-headline">
                Inadimplencia Critica Detectada
              </h3>
              <p className="text-sm text-stone-400">
                Existem {delinquencyAlerts.length} faturas com mais de 60 dias de atraso que requerem acao imediata.
              </p>
            </div>
          </div>
          <Button variant="danger" size="sm" icon="arrow_forward">
            Ver Pendencias
          </Button>
        </div>
      </section>

      {/* Stats */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="account_balance_wallet"
          label="Faturamento Mensal"
          value={kpi?.faturamentoMensal ?? "R$ 0"}
          delta="+8.4%"
          deltaType="up"
        />
        <StatCard
          icon="pending_actions"
          label="A Receber"
          value={kpi?.aReceber ?? "R$ 0"}
          delta={`${billingRecords.filter(r => r.status === "pending").length} faturas`}
          deltaType="neutral"
        />
        <StatCard
          icon="assignment_late"
          label="Inadimplencia"
          value={kpi?.inadimplencia ?? "0%"}
          delta="-1.2%"
          deltaType="down"
        />
        <StatCard
          icon="check_circle"
          label="Taxa de Pagamento"
          value={kpi?.taxaPagamento ?? "0%"}
          delta="+1.2%"
          deltaType="up"
        />
      </section>

      {/* Chart + Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Cash Flow Chart */}
        <Card className="lg:col-span-2" padding="lg">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold font-headline">Fluxo de Caixa Mensal</h3>
              <p className="text-xs text-stone-400">Comparativo de Entradas vs Projecoes</p>
            </div>
            <div className="flex gap-4">
              <span className="flex items-center gap-1.5 text-[10px] text-stone-400">
                <span className="w-2 h-2 rounded-full bg-primary" /> Entradas
              </span>
              <span className="flex items-center gap-1.5 text-[10px] text-stone-400">
                <span className="w-2 h-2 rounded-full bg-stone-700" /> Projecao
              </span>
            </div>
          </div>
          <div className="h-48 md:h-64 flex items-end justify-between gap-2 md:gap-4 px-2">
            {cashFlowMonths.map((m) => (
              <div key={m.label} className="flex flex-col items-center flex-1 group">
                <div
                  className="w-full bg-stone-800 rounded-t-sm relative"
                  style={{ height: `${m.projecao}%` }}
                >
                  <div
                    className="absolute bottom-0 w-full bg-primary/50 group-hover:bg-primary rounded-t-sm transition-all"
                    style={{ height: `${m.entrada}%` }}
                  />
                </div>
                <span className="text-[10px] mt-2 text-stone-500 font-bold uppercase">
                  {m.label}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Quick Actions */}
        <Card padding="lg" className="flex flex-col">
          <h3 className="text-xl font-bold font-headline mb-6">Acoes Rapidas</h3>
          <div className="space-y-3 flex-1">
            <Button className="w-full justify-between" icon="send" size="md">
              Cobranca em Massa
            </Button>
            <Button variant="secondary" className="w-full justify-between" icon="download" size="md">
              Exportar Relatorios
            </Button>
            <Button variant="secondary" className="w-full justify-between" icon="receipt_long" size="md">
              Gerar Fatura
            </Button>
          </div>
          <div className="mt-auto pt-6">
            <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
              <span className="text-[10px] uppercase tracking-wider text-primary font-bold">
                Resumo de Hoje
              </span>
              <div className="flex items-center justify-between mt-2">
                <span className="text-sm text-on-surface">Pagamentos Recebidos</span>
                <span className="font-bold text-primary">R$ 4.250</span>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter Tabs + Period */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-2 overflow-x-auto pb-2 md:pb-0">
          {filterButtons.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilterStatus(f.value)}
              className={cn(
                "px-4 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors",
                filterStatus === f.value
                  ? "bg-primary text-on-primary-container"
                  : "bg-surface-container-highest text-stone-300 hover:bg-white/10",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-stone-400 font-bold uppercase">Periodo:</label>
          <select
            value={filterPeriod}
            onChange={(e) => setFilterPeriod(e.target.value)}
            className="bg-surface-container-low border border-outline-variant/30 rounded-lg px-3 py-1.5 text-sm text-on-surface focus:outline-none focus:border-primary-container"
          >
            <option value="2026-04">Abril 2026</option>
            <option value="2026-03">Marco 2026</option>
            <option value="2026-02">Fevereiro 2026</option>
            <option value="2026-01">Janeiro 2026</option>
          </select>
        </div>
      </div>

      {/* Billing Table */}
      <section>
        <DataTable columns={columns} data={tableData} />
        <div className="flex items-center justify-between mt-4 px-2">
          <span className="text-xs text-stone-500">
            Mostrando 1-{filtered.length} de {billingRecords.length} faturas
          </span>
          <div className="flex gap-2">
            <button className="p-2 rounded-lg border border-outline-variant/20 text-stone-400 hover:bg-white/5 transition-all">
              <MaterialIcon icon="chevron_left" size="sm" />
            </button>
            <button className="p-2 rounded-lg border border-outline-variant/20 text-stone-400 hover:bg-white/5 transition-all">
              <MaterialIcon icon="chevron_right" size="sm" />
            </button>
          </div>
        </div>
      </section>

      {/* Delinquency Alerts */}
      <section>
        <h3 className="text-xl font-bold font-headline mb-4 flex items-center gap-2">
          <MaterialIcon icon="notification_important" className="text-error" />
          Alertas de Inadimplencia
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {delinquencyAlerts.map((alert) => (
            <Card
              key={alert.invoiceId}
              padding="sm"
              className={cn(
                "border-l-4",
                alert.daysLate >= 60 ? "border-l-error" : "border-l-amber-500",
              )}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-on-surface text-sm">{alert.patient}</p>
                  <p className="text-[10px] text-stone-500">{alert.invoiceId}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-on-surface text-sm">
                    {formatCurrency(alert.amount)}
                  </p>
                  <Badge tone={alert.daysLate >= 60 ? "danger" : "warning"}>
                    {alert.daysLate} dias de atraso
                  </Badge>
                </div>
              </div>
              <div className="mt-3">
                <ProgressBar
                  value={Math.min(100, (alert.daysLate / 90) * 100)}
                  variant={alert.daysLate >= 60 ? "danger" : "warning"}
                  size="sm"
                />
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
