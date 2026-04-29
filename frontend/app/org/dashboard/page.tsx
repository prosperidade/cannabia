"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/cn";
import { getOrgDashboard } from "@/lib/api";
import {
  Card,
  StatCard,
  MaterialIcon,
  Badge,
  Button,
  Avatar,
  ProgressBar,
} from "@/components/ui-tw";

type KpiItem = { icon: string; label: string; value: string; delta: string; deltaType: "up" | "down" | "neutral" };
type ChartConsulta = { month: string; novo: number; retorno: number };
type ChartReceita = { month: string; value: number };
type TopMedico = { name: string; specialty: string; count: number; rating: number | null };
type ActivityItem = { icon: string; text: string; time: string; tone: "primary" | "success" | "info" | "danger" };

type OrgDashData = {
  kpiData: KpiItem[];
  chartConsultas: ChartConsulta[];
  chartReceita: ChartReceita[];
  topMedicos: TopMedico[];
  recentActivity: ActivityItem[];
};

export default function OrgDashboardPage() {
  const [period] = useState("6m");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<OrgDashData | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const res = await getOrgDashboard();
        if (cancelled) return;
        setData(res.data as unknown as OrgDashData);
      } catch {
        if (!cancelled) setError("Nao foi possivel carregar o painel gerencial.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchData();
    return () => { cancelled = true; };
  }, []);

  const kpiData = data?.kpiData ?? [];
  const chartConsultas = data?.chartConsultas ?? [];
  const chartReceita = data?.chartReceita ?? [];
  const topMedicos = data?.topMedicos ?? [];
  const recentActivity = data?.recentActivity ?? [];

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando painel gerencial...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <MaterialIcon icon="cloud_off" size="xl" className="text-error/50 mb-4" />
          <p className="text-on-surface-variant text-sm">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8 space-y-8 pb-28 md:pb-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-extrabold font-headline tracking-tight">
            Painel Gerencial
          </h2>
          <p className="text-on-surface-variant text-sm font-body">
            Visao em tempo real das operacoes clinicas e organizacionais.
          </p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" size="sm" icon="download">
            Exportar
          </Button>
          <Button variant="primary" size="sm" icon="refresh">
            Atualizar
          </Button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4">
        {kpiData.map((kpi) => (
          <StatCard
            key={kpi.label}
            icon={kpi.icon}
            label={kpi.label}
            value={kpi.value}
            delta={kpi.delta}
            deltaType={kpi.deltaType}
          />
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Consultas por Periodo */}
        <Card variant="glass" padding="lg" className="xl:col-span-8">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between mb-6 gap-4">
            <div>
              <h4 className="text-lg font-bold font-headline">Consultas por Periodo</h4>
              <p className="text-sm text-on-surface-variant">Novos pacientes vs retornos</p>
            </div>
            <select className="bg-surface-container border-none text-xs rounded-full px-4 py-2 focus:ring-1 focus:ring-primary text-on-surface">
              <option>Ultimos 6 meses</option>
              <option>Ultimo ano</option>
            </select>
          </div>
          {/* Bar Chart (simulated with divs) */}
          <div className="h-52 md:h-64 flex items-end justify-between gap-2">
            {chartConsultas.map((d) => (
              <div key={d.month} className="flex-1 flex flex-col items-center group">
                <div className="w-full flex gap-1 items-end h-full">
                  <div
                    className="bg-primary/20 w-1/2 rounded-t-sm group-hover:bg-primary/40 transition-all"
                    style={{ height: `${d.retorno}%` }}
                  />
                  <div
                    className="bg-primary w-1/2 rounded-t-sm"
                    style={{ height: `${d.novo + 10}%` }}
                  />
                </div>
                <span className="text-[10px] text-stone-500 mt-2 font-bold uppercase">
                  {d.month}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-6 flex gap-6">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-primary" />
              <span className="text-xs text-on-surface-variant">Novos Pacientes</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-primary/20" />
              <span className="text-xs text-on-surface-variant">Retornos</span>
            </div>
          </div>
        </Card>

        {/* Receita por Periodo */}
        <Card variant="glass" padding="lg" className="xl:col-span-4">
          <h4 className="text-lg font-bold font-headline mb-2">Receita por Periodo</h4>
          <p className="text-sm text-on-surface-variant mb-6">Valor mensal (R$ mil)</p>
          <div className="h-40 flex items-end justify-between gap-2">
            {chartReceita.map((d) => (
              <div key={d.month} className="flex-1 flex flex-col items-center group">
                <div
                  className="w-full bg-primary rounded-t-sm group-hover:brightness-110 transition-all"
                  style={{ height: `${(d.value / 45) * 100}%` }}
                />
                <span className="text-[10px] text-stone-500 mt-2 font-bold uppercase">
                  {d.month}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Second Row: Top Medicos + Status + Activity */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Top Medicos */}
        <Card variant="glass" padding="md" className="xl:col-span-4">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-lg font-bold font-headline flex items-center gap-2">
              <MaterialIcon icon="emoji_events" className="text-primary" />
              Top Medicos
            </h4>
            <button className="text-primary text-xs font-bold hover:underline">Ver todos</button>
          </div>
          <div className="space-y-4">
            {topMedicos.map((doc, idx) => (
              <div
                key={doc.name}
                className="flex items-center justify-between p-3 rounded-xl bg-surface-container/50 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="w-6 h-6 flex items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-black">
                    {idx + 1}
                  </span>
                  <Avatar name={doc.name} size="sm" />
                  <div>
                    <p className="text-sm font-bold">{doc.name}</p>
                    <p className="text-[10px] text-stone-500">{doc.specialty}</p>
                  </div>
                </div>
                <div className="text-right">
                  {doc.rating !== null ? (
                    <div className="flex items-center gap-1 text-primary">
                      <MaterialIcon icon="star" filled size="sm" />
                      <span className="text-sm font-bold">{doc.rating}</span>
                    </div>
                  ) : (
                    <span className="text-[10px] text-stone-500">sem avaliacao</span>
                  )}
                  <p className="text-[10px] text-stone-500">{doc.count} consultas</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Status Operacional */}
        <Card variant="glass" padding="md" className="xl:col-span-4 border-t-2 border-primary">
          <h4 className="text-lg font-bold font-headline mb-4 flex items-center gap-2">
            <MaterialIcon icon="eco" className="text-primary" />
            Status Operacional
          </h4>
          <div className="space-y-3">
            {/* Agendamentos Hoje */}
            <div className="flex items-center justify-between p-3 bg-surface-container/40 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <MaterialIcon icon="event_available" className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-bold">Agendamentos Hoje</p>
                  <p className="text-[10px] text-stone-500">24 confirmados - 3 pendentes</p>
                </div>
              </div>
              <MaterialIcon icon="chevron_right" className="text-stone-600" />
            </div>
            {/* Retornos Pendentes */}
            <div className="flex items-center justify-between p-3 bg-surface-container/40 rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-tertiary/10 flex items-center justify-center">
                  <MaterialIcon icon="sync_problem" className="text-tertiary" />
                </div>
                <div>
                  <p className="text-sm font-bold">Retornos Pendentes</p>
                  <p className="text-[10px] text-stone-500">12 pacientes aguardando retorno</p>
                </div>
              </div>
              <MaterialIcon icon="chevron_right" className="text-stone-600" />
            </div>
            {/* Alertas IA */}
            <div className="flex items-center justify-between p-3 bg-error/5 rounded-xl border border-error/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-error/10 flex items-center justify-center">
                  <MaterialIcon icon="inventory_2" className="text-error" />
                </div>
                <div>
                  <p className="text-sm font-bold text-error">Alerta de Estoque</p>
                  <p className="text-[10px] text-stone-500">CBD Full Spectrum baixo (4 unid.)</p>
                </div>
              </div>
              <MaterialIcon icon="priority_high" className="text-error" />
            </div>
            {/* AI Alert */}
            <div className="flex items-center justify-between p-3 bg-surface-container/40 rounded-xl border border-primary/10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <MaterialIcon icon="psychology" className="text-primary" />
                </div>
                <div>
                  <p className="text-sm font-bold">Alertas IA</p>
                  <p className="text-[10px] text-stone-500">3 sugestoes de ajuste terapeutico</p>
                </div>
              </div>
              <Badge tone="primary">3</Badge>
            </div>
          </div>
          <button className="w-full mt-4 py-2 bg-surface-container rounded-lg text-xs font-bold hover:bg-surface-container-highest transition-all">
            Ver Todos os Alertas
          </button>
        </Card>

        {/* Atividade Recente */}
        <Card variant="glass" padding="md" className="xl:col-span-4">
          <h4 className="text-lg font-bold font-headline mb-4 flex items-center gap-2">
            <MaterialIcon icon="history" className="text-primary" />
            Atividade Recente
          </h4>
          <div className="space-y-3">
            {recentActivity.map((act, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors"
              >
                <div className={cn(
                  "w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0",
                  act.tone === "primary" && "bg-primary/10",
                  act.tone === "success" && "bg-emerald-500/10",
                  act.tone === "info" && "bg-blue-400/10",
                  act.tone === "danger" && "bg-error/10",
                )}>
                  <MaterialIcon
                    icon={act.icon}
                    size="sm"
                    className={cn(
                      act.tone === "primary" && "text-primary",
                      act.tone === "success" && "text-emerald-400",
                      act.tone === "info" && "text-blue-400",
                      act.tone === "danger" && "text-error",
                    )}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-on-surface">{act.text}</p>
                  <p className="text-[10px] text-stone-500 mt-0.5">{act.time}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Clinical Performance Table */}
      <Card variant="glass" padding="sm" className="overflow-hidden">
        <div className="p-5 border-b border-white/5 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h4 className="text-lg font-bold font-headline">Desempenho Clinico</h4>
            <p className="text-sm text-on-surface-variant">Top profissionais por eficacia e volume de atendimentos</p>
          </div>
          <button className="text-primary text-xs font-bold hover:underline">
            Ver Corpo Medico
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-container/40 text-[10px] uppercase tracking-widest text-stone-500 font-bold">
              <tr>
                <th className="px-5 md:px-8 py-4">Profissional</th>
                <th className="px-5 md:px-8 py-4">Especialidade</th>
                <th className="px-5 md:px-8 py-4">Pacientes</th>
                <th className="px-5 md:px-8 py-4">Avaliacao</th>
                <th className="px-5 md:px-8 py-4">Indice de Resultado</th>
                <th className="px-5 md:px-8 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {(data?.topMedicos ?? []).length > 0 ? (
                (data?.topMedicos ?? []).map((doc) => (
                  <tr key={doc.name} className="hover:bg-white/5 transition-colors">
                    <td className="px-5 md:px-8 py-4">
                      <div className="flex items-center gap-3">
                        <Avatar name={doc.name} size="sm" />
                        <span className="font-bold">{doc.name}</span>
                      </div>
                    </td>
                    <td className="px-5 md:px-8 py-4 text-on-surface-variant">{doc.specialty}</td>
                    <td className="px-5 md:px-8 py-4">{doc.count}</td>
                    <td className="px-5 md:px-8 py-4">
                      {doc.rating !== null ? (
                        <div className="flex items-center gap-1 text-primary">
                          <MaterialIcon icon="star" filled size="sm" />
                          <span className="font-bold">{doc.rating}</span>
                        </div>
                      ) : (
                        <span className="text-stone-500 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-5 md:px-8 py-4">
                      {doc.rating !== null ? (
                        <ProgressBar value={Math.round(doc.rating * 20)} size="sm" glow />
                      ) : (
                        <span className="text-stone-500 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-5 md:px-8 py-4">
                      <Badge tone="primary">Ativo</Badge>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-stone-500 text-sm">
                    Dados de desempenho serao exibidos quando houver atendimentos suficientes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
