"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { getOrgFinancial } from "@/lib/api";
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

/* ── Types ─────────────────────────────────────────────────────────── */

type RevenueItem = { label: string; value: number; pct: number; color: string };
type CostItem = { label: string; value: number; pct: number };
type DoctorTransfer = {
  id: number;
  name: string;
  specialty: string;
  splitPct: number;
  consultations: number;
  grossRevenue: number;
  netPayout: number;
  status: "paid" | "pending";
  transferDate: string | null;
};
type GrowthMonth = { label: string; pct: number };

type FinancialData = {
  revenueBreakdown: RevenueItem[];
  costBreakdown: CostItem[];
  doctorTransfers: DoctorTransfer[];
  revenueGrowthMonths: GrowthMonth[];
  totalRevenue: number;
  totalCosts: number;
};

/* ── Helper ────────────────────────────────────────────────────────── */

const formatCurrency = (v: number) =>
  v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/* ── Page Component ────────────────────────────────────────────────── */

export default function FinanceiroPage() {
  const { data: session } = useApiSession();
  const [periodRange, setPeriodRange] = useState("2026-04");
  const [data, setData] = useState<FinancialData | null>(null);
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchFinancial() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await getOrgFinancial();
        if (cancelled) return;
        setData(res.data as unknown as FinancialData);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar os dados financeiros.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchFinancial();
    return () => {
      cancelled = true;
    };
  }, []);

  const revenueBreakdown = data?.revenueBreakdown ?? [];
  const costBreakdown = data?.costBreakdown ?? [];
  const doctorTransfers = data?.doctorTransfers ?? [];
  const revenueGrowthMonths = data?.revenueGrowthMonths ?? [];
  const totalRevenue = data?.totalRevenue ?? 0;
  const totalCosts = data?.totalCosts ?? 0;
  const netProfit = totalRevenue - totalCosts;
  const margin = totalRevenue > 0 ? ((netProfit / totalRevenue) * 100).toFixed(1) : "0.0";

  const transferColumns: DataTableColumn[] = [
    {
      key: "name",
      label: "Medico",
      sortable: true,
      render: (_val, row) => (
        <div>
          <div className="text-sm font-bold text-on-surface">{row.name as string}</div>
          <div className="text-[10px] text-stone-500">
            {row.specialty as string} &bull; {row.splitPct as number}/
            {100 - (row.splitPct as number)} Repasse
          </div>
        </div>
      ),
    },
    {
      key: "consultations",
      label: "Consultas",
      sortable: true,
      render: (val) => <span className="font-semibold">{val as number}</span>,
    },
    {
      key: "grossRevenue",
      label: "Receita Bruta",
      sortable: true,
      render: (val) => <span className="text-stone-300">{formatCurrency(val as number)}</span>,
    },
    {
      key: "netPayout",
      label: "Valor Repasse",
      sortable: true,
      render: (val) => (
        <span className="font-headline font-bold text-on-surface">
          {formatCurrency(val as number)}
        </span>
      ),
    },
    {
      key: "status",
      label: "Status Repasse",
      render: (val) => {
        const isPaid = val === "paid";
        return <Badge tone={isPaid ? "success" : "warning"}>{isPaid ? "Pago" : "Pendente"}</Badge>;
      },
    },
    {
      key: "transferDate",
      label: "Data Repasse",
      render: (val) =>
        val ? (
          new Date(val as string).toLocaleDateString("pt-BR")
        ) : (
          <span className="text-stone-600">Pendente</span>
        ),
    },
  ];

  const tableData = doctorTransfers.map((d) => ({ ...d }));

  if (apiLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando financeiro...</p>
        </div>
      </div>
    );
  }

  if (apiError && !data) {
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
          Financeiro Gerencial
        </h1>
        <p className="text-on-surface/60 mt-1 text-sm md:text-base">Controle e Repasses</p>
      </header>

      {/* KPI Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="monetization_on"
          label="Receita Bruta"
          value={formatCurrency(totalRevenue)}
          delta="+12%"
          deltaType="up"
        />
        <StatCard
          icon="money_off"
          label="Custos Operacionais"
          value={formatCurrency(totalCosts)}
          delta="+3.1%"
          deltaType="down"
        />
        <StatCard
          icon="savings"
          label="Lucro Liquido"
          value={formatCurrency(netProfit)}
          delta="+15.2%"
          deltaType="up"
        />
        <StatCard
          icon="percent"
          label="Margem"
          value={`${margin}%`}
          delta="+2.1pp"
          deltaType="up"
        />
      </section>

      {/* Revenue Chart + Revenue Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Growth Chart */}
        <Card className="lg:col-span-2" padding="lg">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h3 className="text-xl font-bold font-headline">Tendencia de Receita</h3>
              <p className="text-xs text-stone-400">Comparativo mensal de ganhos brutos</p>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1 bg-white/5 text-stone-400 text-xs rounded-full border border-white/5">
                6M
              </button>
              <button className="px-3 py-1 bg-primary text-on-primary-container text-xs font-bold rounded-full">
                1A
              </button>
            </div>
          </div>
          <div className="h-48 md:h-64 flex items-end justify-between gap-2 px-2">
            {revenueGrowthMonths.map((m, i) => (
              <div key={m.label} className="w-full relative group" style={{ height: `${m.pct}%` }}>
                <div className="absolute inset-x-0 bottom-0 bg-primary/40 group-hover:bg-primary transition-colors rounded-t-md h-full" />
                <span
                  className={cn(
                    "absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] uppercase font-bold",
                    i === revenueGrowthMonths.length - 2 ? "text-primary" : "text-stone-500",
                  )}
                >
                  {m.label}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Revenue Breakdown */}
        <Card padding="lg">
          <h3 className="text-lg font-bold font-headline mb-6">Composicao da Receita</h3>
          {/* Stacked Bar */}
          <div className="flex h-6 rounded-full overflow-hidden mb-6">
            {revenueBreakdown.map((item) => (
              <div
                key={item.label}
                className={cn(item.color, "transition-all")}
                style={{ width: `${item.pct}%` }}
                title={`${item.label}: ${item.pct}%`}
              />
            ))}
          </div>
          <div className="space-y-4">
            {revenueBreakdown.map((item) => (
              <div key={item.label} className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={cn("w-3 h-3 rounded-full", item.color)} />
                  <span className="text-sm text-on-surface">{item.label}</span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-on-surface">
                    {formatCurrency(item.value)}
                  </span>
                  <span className="text-[10px] text-stone-500 ml-2">{item.pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Cost Breakdown */}
      <Card padding="lg">
        <h3 className="text-xl font-bold font-headline mb-6 flex items-center gap-2">
          <MaterialIcon icon="pie_chart" className="text-primary" />
          Detalhamento de Custos
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {costBreakdown.map((cost) => (
            <div
              key={cost.label}
              className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/20"
            >
              <p className="text-[10px] uppercase tracking-wider text-stone-500 font-bold mb-2">
                {cost.label}
              </p>
              <p className="text-xl font-headline font-bold text-on-surface">
                {formatCurrency(cost.value)}
              </p>
              <div className="mt-3 flex items-center gap-2">
                <ProgressBar value={cost.pct} variant="primary" size="sm" className="flex-1" />
                <span className="text-[10px] text-stone-400 font-bold">{cost.pct}%</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Doctor Transfers Table */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-bold font-headline flex items-center gap-2">
            <MaterialIcon icon="group" className="text-primary" />
            Repasses Medicos
          </h3>
          <Button variant="secondary" size="sm" icon="send">
            Processar Repasses
          </Button>
        </div>
        <DataTable columns={transferColumns} data={tableData} />
      </section>

      {/* P&L Summary */}
      <Card padding="lg" className="border border-primary/10">
        <h3 className="text-xl font-bold font-headline mb-6 flex items-center gap-2">
          <MaterialIcon icon="summarize" className="text-primary" filled />
          Resumo DRE Mensal
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Revenue */}
          <div className="space-y-3">
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">
              Receitas
            </p>
            <div className="space-y-2">
              {revenueBreakdown.map((item) => (
                <div key={item.label} className="flex justify-between text-sm">
                  <span className="text-stone-400">{item.label}</span>
                  <span className="text-on-surface font-medium">{formatCurrency(item.value)}</span>
                </div>
              ))}
              <div className="flex justify-between text-sm pt-2 border-t border-white/5">
                <span className="font-bold text-on-surface">Total Receitas</span>
                <span className="font-bold text-primary">{formatCurrency(totalRevenue)}</span>
              </div>
            </div>
          </div>

          {/* Costs */}
          <div className="space-y-3">
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold">Custos</p>
            <div className="space-y-2">
              {costBreakdown.map((item) => (
                <div key={item.label} className="flex justify-between text-sm">
                  <span className="text-stone-400">{item.label}</span>
                  <span className="text-on-surface font-medium">
                    ({formatCurrency(item.value)})
                  </span>
                </div>
              ))}
              <div className="flex justify-between text-sm pt-2 border-t border-white/5">
                <span className="font-bold text-on-surface">Total Custos</span>
                <span className="font-bold text-error">({formatCurrency(totalCosts)})</span>
              </div>
            </div>
          </div>

          {/* Result */}
          <div className="flex flex-col justify-center items-center bg-primary/5 rounded-2xl p-6 border border-primary/10">
            <p className="text-[10px] uppercase tracking-widest text-stone-500 font-bold mb-2">
              Resultado Liquido
            </p>
            <p className="text-3xl font-headline font-extrabold text-primary">
              {formatCurrency(netProfit)}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Badge tone="success">Margem {margin}%</Badge>
            </div>
            <div className="mt-4 w-full">
              <ProgressBar value={parseFloat(margin)} variant="primary" glow />
            </div>
          </div>
        </div>
      </Card>

      {/* AI Insight */}
      <Card
        padding="md"
        className="bg-gradient-to-br from-primary/5 to-transparent border border-primary/10"
      >
        <div className="flex items-center gap-2 text-primary mb-2">
          <MaterialIcon icon="auto_awesome" size="sm" />
          <span className="text-[10px] font-black uppercase tracking-widest">
            Analise Inteligente
          </span>
        </div>
        <p className="text-sm text-on-surface leading-relaxed">
          Analises preditivas serao geradas automaticamente quando houver dados financeiros
          suficientes para identificar tendencias.
        </p>
      </Card>
    </div>
  );
}
