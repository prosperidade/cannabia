"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { listOrgPatients } from "@/lib/api";
import {
  Card,
  StatCard,
  Badge,
  Button,
  SearchBar,
  MaterialIcon,
  Avatar,
  DataTable,
  type DataTableColumn,
} from "@/components/ui-tw";

type PatientStatus = "em_tratamento" | "onboarding" | "aguardando" | "inativo";

interface OrgPatient {
  id: string;
  nome: string;
  telefone: string;
  status: PatientStatus;
  tratamento: string;
  ultimoContato: string;
  medicoResponsavel: string;
}

const statusConfig: Record<PatientStatus, { label: string; tone: "primary" | "info" | "warning" | "danger" | "neutral" }> = {
  em_tratamento: { label: "Em Tratamento", tone: "primary" },
  onboarding: { label: "Em Cadastro", tone: "info" },
  aguardando: { label: "Aguardando Retorno", tone: "warning" },
  inativo: { label: "Inativo", tone: "danger" },
};

type StatsData = {
  total: number;
  ativos: number;
  emTratamento: number;
  inativos: number;
};

const tratamentos = ["Todos", "Ansiedade", "Dor Cronica", "Insonia", "Depressao", "Epilepsia", "Fibromialgia", "TDAH", "Dor Neuropatica", "Parkinson"];

export default function PacientesPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("todos");
  const [tratamentoFilter, setTratamentoFilter] = useState<string>("Todos");
  const [patients, setPatients] = useState<OrgPatient[]>([]);
  const [statsData, setStatsData] = useState<StatsData>({ total: 0, ativos: 0, emTratamento: 0, inativos: 0 });
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchPatients() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await listOrgPatients({
          search: search || undefined,
          status: statusFilter !== "todos" ? statusFilter : undefined,
        });
        if (cancelled) return;
        const d = res.data as Record<string, unknown>;
        setPatients((d.patients as OrgPatient[]) ?? []);
        if (d.stats) setStatsData(d.stats as StatsData);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar a lista de pacientes.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchPatients();
    return () => { cancelled = true; };
  }, [search, statusFilter]);

  const filteredPatients = useMemo(() => {
    return patients.filter((p) => {
      const matchesTratamento =
        tratamentoFilter === "Todos" || p.tratamento === tratamentoFilter;
      return matchesTratamento;
    });
  }, [patients, tratamentoFilter]);

  const columns: DataTableColumn[] = [
    {
      key: "nome",
      label: "Nome",
      sortable: true,
      render: (_val, row) => {
        const nome = row.nome as string;
        return (
          <div className="flex items-center gap-3">
            <Avatar name={nome} size="sm" />
            <div>
              <p className="text-sm font-bold text-on-surface">{nome}</p>
            </div>
          </div>
        );
      },
    },
    {
      key: "telefone",
      label: "Telefone",
      render: (val) => <span className="text-on-surface-variant">{String(val)}</span>,
    },
    {
      key: "status",
      label: "Status",
      sortable: true,
      render: (val) => {
        const st = val as PatientStatus;
        const cfg = statusConfig[st];
        return (
          <Badge tone={cfg.tone} pulse={st === "em_tratamento"}>
            {cfg.label}
          </Badge>
        );
      },
    },
    {
      key: "tratamento",
      label: "Tratamento",
      sortable: true,
      render: (val) => (
        <span className="bg-surface-variant/50 px-2.5 py-1 rounded-md text-xs border border-white/5 text-on-surface-variant">
          {String(val)}
        </span>
      ),
    },
    {
      key: "ultimoContato",
      label: "Ultimo Contato",
      sortable: true,
      render: (val) => <span className="text-stone-400">{String(val)}</span>,
    },
    {
      key: "medicoResponsavel",
      label: "Medico Responsavel",
      render: (val) => <span className="text-stone-300">{String(val)}</span>,
    },
    {
      key: "id",
      label: "Acoes",
      render: (_val, row) => (
        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            className="p-2 text-stone-400 hover:text-primary hover:bg-primary/10 rounded-lg transition-all"
            onClick={(e) => {
              e.stopPropagation();
              router.push(`/med/prontuario/${row.id}`);
            }}
          >
            <MaterialIcon icon="visibility" size="sm" />
          </button>
          <button className="p-2 text-stone-400 hover:text-primary hover:bg-primary/10 rounded-lg transition-all">
            <MaterialIcon icon="edit" size="sm" />
          </button>
          <button className="p-2 text-stone-400 hover:text-error hover:bg-error/10 rounded-lg transition-all">
            <MaterialIcon icon="delete" size="sm" />
          </button>
        </div>
      ),
    },
  ];

  const tableData = filteredPatients.map((p) => ({
    id: p.id,
    nome: p.nome,
    telefone: p.telefone,
    status: p.status,
    tratamento: p.tratamento,
    ultimoContato: p.ultimoContato,
    medicoResponsavel: p.medicoResponsavel,
  }));

  if (apiLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando pacientes...</p>
        </div>
      </div>
    );
  }

  if (apiError && patients.length === 0) {
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
    <div className="p-4 md:p-8 space-y-8 pb-28 md:pb-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-extrabold font-headline tracking-tight">
            Gestao de Pacientes
          </h2>
          <p className="text-on-surface-variant text-sm font-body">
            Gerenciamento completo do cadastro e tratamento de pacientes.
          </p>
        </div>
        <Button variant="primary" size="sm" icon="person_add">
          Novo Paciente
        </Button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon="group" label="Total" value={statsData.total.toLocaleString("pt-BR")} delta="+12%" deltaType="up" />
        <StatCard icon="check_circle" label="Ativos" value={statsData.ativos.toLocaleString("pt-BR")} delta="+8%" deltaType="up" />
        <StatCard icon="healing" label="Em Tratamento" value={statsData.emTratamento.toLocaleString("pt-BR")} delta="+5%" deltaType="up" />
        <StatCard icon="person_off" label="Inativos" value={statsData.inativos.toLocaleString("pt-BR")} delta="-3%" deltaType="down" />
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar paciente por nome ou telefone..."
          className="flex-1"
        />
        <div className="flex gap-3 flex-wrap">
          <div className="glass-panel rounded-xl px-4 py-2 flex items-center gap-2">
            <span className="text-xs text-stone-500">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-transparent border-none p-0 text-xs font-bold text-primary focus:ring-0 cursor-pointer"
            >
              <option value="todos">Todos</option>
              <option value="em_tratamento">Em Tratamento</option>
              <option value="onboarding">Em Cadastro</option>
              <option value="aguardando">Aguardando</option>
              <option value="inativo">Inativo</option>
            </select>
          </div>
          <div className="glass-panel rounded-xl px-4 py-2 flex items-center gap-2">
            <span className="text-xs text-stone-500">Tratamento:</span>
            <select
              value={tratamentoFilter}
              onChange={(e) => setTratamentoFilter(e.target.value)}
              className="bg-transparent border-none p-0 text-xs font-bold text-primary focus:ring-0 cursor-pointer"
            >
              {tratamentos.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Table Section */}
      <div>
        <div className="flex items-center gap-2 mb-4 px-1">
          <span className="w-2 h-6 bg-primary rounded-full" />
          <h3 className="text-lg font-headline font-bold text-on-surface">Lista de Pacientes</h3>
        </div>

        <DataTable
          columns={columns}
          data={tableData}
          onRowClick={(row) => router.push(`/med/prontuario/${row.id}`)}
          emptyMessage="Nenhum paciente encontrado para os filtros selecionados."
        />

        {/* Pagination */}
        <div className="mt-6 flex flex-col md:flex-row items-center justify-between gap-4 px-2">
          <p className="text-xs text-stone-500 font-medium">
            Mostrando <span className="text-on-surface">1 - {filteredPatients.length}</span> de{" "}
            {statsData.total.toLocaleString("pt-BR")} pacientes
          </p>
          <div className="flex items-center gap-2">
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-white/5 text-stone-500 hover:bg-white/5 transition-all">
              <MaterialIcon icon="chevron_left" size="sm" />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg bg-primary text-on-primary font-bold text-xs">
              1
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-white/5 text-stone-400 hover:bg-white/5 transition-all text-xs">
              2
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-white/5 text-stone-400 hover:bg-white/5 transition-all text-xs">
              3
            </button>
            <span className="text-stone-600 px-1">...</span>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-white/5 text-stone-400 hover:bg-white/5 transition-all text-xs">
              48
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-lg border border-white/5 text-stone-500 hover:bg-white/5 transition-all">
              <MaterialIcon icon="chevron_right" size="sm" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
