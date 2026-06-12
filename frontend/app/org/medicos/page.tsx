"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { listOrgDoctors } from "@/lib/api";
import {
  Card,
  StatCard,
  Badge,
  Button,
  SearchBar,
  MaterialIcon,
  Avatar,
  DataTable,
  ProgressBar,
  type DataTableColumn,
} from "@/components/ui-tw";

type DoctorStatus = "ativo" | "licenca" | "avaliacao" | "offline";

interface OrgDoctor {
  id: string;
  nome: string;
  crm: string;
  especialidade: string;
  status: DoctorStatus;
  pacientesAtivos: number;
  rating: number;
  consultasHoje: number;
  email: string;
  crmVerificado: boolean;
  documentosPendentes: number;
  ultimoTreinamento: string;
  retencao: number;
  eficiencia: number;
}

const statusConfig: Record<
  DoctorStatus,
  { label: string; tone: "primary" | "warning" | "info" | "neutral" }
> = {
  ativo: { label: "Ativo", tone: "primary" },
  licenca: { label: "Licenca", tone: "warning" },
  avaliacao: { label: "Em Avaliacao", tone: "info" },
  offline: { label: "Indisponivel", tone: "neutral" },
};

type DoctorStats = {
  total: number;
  ativos: number;
  emAvaliacao: number;
  consultasHoje: number;
};

export default function MedicosPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"painel" | "credenciais">("painel");
  const [search, setSearch] = useState("");
  const [doctors, setDoctors] = useState<OrgDoctor[]>([]);
  const [statsData, setStatsData] = useState<DoctorStats>({
    total: 0,
    ativos: 0,
    emAvaliacao: 0,
    consultasHoje: 0,
  });
  const [apiLoading, setApiLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchDoctors() {
      try {
        setApiLoading(true);
        setApiError(null);
        const res = await listOrgDoctors();
        if (cancelled) return;
        const d = res.data as Record<string, unknown>;
        setDoctors((d.doctors as OrgDoctor[]) ?? []);
        if (d.stats) setStatsData(d.stats as DoctorStats);
      } catch {
        if (!cancelled) setApiError("Nao foi possivel carregar o corpo medico.");
      } finally {
        if (!cancelled) setApiLoading(false);
      }
    }
    fetchDoctors();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredDoctors = doctors.filter((d) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      d.nome.toLowerCase().includes(s) ||
      d.crm.toLowerCase().includes(s) ||
      d.especialidade.toLowerCase().includes(s)
    );
  });

  /* ── Credenciais Tab Table Columns ── */
  const credenciaisColumns: DataTableColumn[] = [
    {
      key: "nome",
      label: "Profissional",
      sortable: true,
      render: (_val, row) => {
        const nome = row.nome as string;
        const email = row.email as string;
        return (
          <div className="flex items-center gap-3">
            <Avatar name={nome} size="sm" />
            <div>
              <p className="text-sm font-bold text-on-surface">{nome}</p>
              <p className="text-[10px] text-stone-500">{email}</p>
            </div>
          </div>
        );
      },
    },
    {
      key: "crm",
      label: "CRM",
      render: (val) => <span className="font-mono text-xs text-stone-400">{String(val)}</span>,
    },
    {
      key: "crmVerificado",
      label: "Verificacao CRM",
      sortable: true,
      render: (val) => {
        const verified = val as boolean;
        return verified ? (
          <div className="flex items-center gap-1.5">
            <MaterialIcon icon="verified" size="sm" className="text-primary" />
            <span className="text-xs text-primary font-bold">Verificado</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <MaterialIcon icon="warning" size="sm" className="text-error" />
            <span className="text-xs text-error font-bold">Pendente</span>
          </div>
        );
      },
    },
    {
      key: "documentosPendentes",
      label: "Documentos",
      sortable: true,
      render: (val) => {
        const count = val as number;
        return count === 0 ? (
          <Badge tone="primary">Completo</Badge>
        ) : (
          <Badge tone="danger">
            {count} pendente{count > 1 ? "s" : ""}
          </Badge>
        );
      },
    },
    {
      key: "ultimoTreinamento",
      label: "Ultimo Treinamento",
      render: (val) => <span className="text-stone-400 text-sm">{String(val)}</span>,
    },
    {
      key: "retencao",
      label: "Retencao",
      sortable: true,
      render: (val) => {
        const v = val as number;
        return v > 0 ? (
          <div className="flex items-center gap-2">
            <ProgressBar value={v} size="sm" className="w-20" />
            <span className="text-xs font-bold text-on-surface">{v}%</span>
          </div>
        ) : (
          <span className="text-stone-500 text-xs">N/A</span>
        );
      },
    },
    {
      key: "eficiencia",
      label: "Eficiencia",
      sortable: true,
      render: (val) => {
        const v = val as number;
        return v > 0 ? (
          <div className="flex items-center gap-2">
            <ProgressBar
              value={v}
              size="sm"
              variant={v >= 90 ? "success" : "warning"}
              className="w-20"
            />
            <span className="text-xs font-bold text-on-surface">{v}%</span>
          </div>
        ) : (
          <span className="text-stone-500 text-xs">N/A</span>
        );
      },
    },
  ];

  const credenciaisData = filteredDoctors.map((d) => ({
    id: d.id,
    nome: d.nome,
    email: d.email,
    crm: d.crm,
    crmVerificado: d.crmVerificado,
    documentosPendentes: d.documentosPendentes,
    ultimoTreinamento: d.ultimoTreinamento,
    retencao: d.retencao,
    eficiencia: d.eficiencia,
  }));

  if (apiLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 rounded-full border-2 border-primary border-t-transparent animate-spin" />
          <p className="text-stone-500 text-sm font-medium">Carregando corpo medico...</p>
        </div>
      </div>
    );
  }

  if (apiError && doctors.length === 0) {
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
          <nav className="flex items-center gap-2 text-stone-500 text-xs uppercase tracking-[0.2em] mb-2">
            <span>Organizacao</span>
            <MaterialIcon icon="chevron_right" size="sm" />
            <span className="text-primary-container">Corpo Medico</span>
          </nav>
          <h2 className="text-2xl md:text-3xl font-extrabold font-headline tracking-tight">
            Gestao de Medicos
          </h2>
        </div>
        <Button
          variant="primary"
          size="sm"
          icon="person_add"
          onClick={() => router.push("/med/onboarding")}
        >
          Novo Medico
        </Button>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon="medical_services"
          label="Total Medicos"
          value={statsData.total}
          delta="+4.2%"
          deltaType="up"
        />
        <StatCard icon="check_circle" label="Ativos" value={statsData.ativos} />
        <StatCard
          icon="pending"
          label="Em Avaliacao"
          value={statsData.emAvaliacao}
          delta="Pendente"
          deltaType="neutral"
        />
        <StatCard
          icon="event_available"
          label="Consultas Hoje"
          value={statsData.consultasHoje}
          delta="+3"
          deltaType="up"
        />
      </div>

      {/* Search + Tabs */}
      <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar medico, CRM ou especialidade..."
          className="flex-1 max-w-md"
        />
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("painel")}
            className={cn(
              "px-5 py-2 rounded-lg text-sm font-bold font-headline transition-all",
              activeTab === "painel"
                ? "bg-primary text-on-primary"
                : "bg-surface-container text-stone-400 hover:text-on-surface hover:bg-surface-container-highest",
            )}
          >
            Painel
          </button>
          <button
            onClick={() => setActiveTab("credenciais")}
            className={cn(
              "px-5 py-2 rounded-lg text-sm font-bold font-headline transition-all",
              activeTab === "credenciais"
                ? "bg-primary text-on-primary"
                : "bg-surface-container text-stone-400 hover:text-on-surface hover:bg-surface-container-highest",
            )}
          >
            Credenciais & Performance
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "painel" ? (
        /* ── Painel Tab: Doctor Cards Grid ── */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDoctors.map((doc) => {
            const stCfg = statusConfig[doc.status];
            return (
              <Card
                key={doc.id}
                variant="glass"
                padding="md"
                className="group hover:border-primary/20 transition-all"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <Avatar name={doc.nome} size="lg" />
                    <div>
                      <h3 className="text-sm font-bold text-on-surface">{doc.nome}</h3>
                      <p className="text-xs text-stone-500 font-mono">{doc.crm}</p>
                      <p className="text-[10px] text-on-surface-variant mt-0.5">
                        {doc.especialidade}
                      </p>
                    </div>
                  </div>
                  <Badge tone={stCfg.tone}>{stCfg.label}</Badge>
                </div>

                {/* Stats Row */}
                <div className="flex items-center justify-between py-3 border-t border-white/5">
                  <div className="text-center">
                    <p className="text-lg font-black text-primary font-headline">
                      {doc.pacientesAtivos}
                    </p>
                    <p className="text-[10px] text-stone-500 uppercase tracking-wider">Pacientes</p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-black text-on-surface font-headline">
                      {doc.consultasHoje}
                    </p>
                    <p className="text-[10px] text-stone-500 uppercase tracking-wider">
                      Consultas Hoje
                    </p>
                  </div>
                  <div className="text-center">
                    {doc.rating > 0 ? (
                      <div className="flex items-center justify-center gap-1">
                        <MaterialIcon icon="star" filled size="sm" className="text-primary" />
                        <span className="text-lg font-black text-on-surface font-headline">
                          {doc.rating}
                        </span>
                      </div>
                    ) : (
                      <span className="text-stone-500 text-sm">N/A</span>
                    )}
                    <p className="text-[10px] text-stone-500 uppercase tracking-wider">Avaliacao</p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 mt-3">
                  <button className="flex-1 py-2 bg-surface-container hover:bg-surface-container-highest text-on-surface text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1">
                    <MaterialIcon icon="event_note" size="sm" />
                    Agenda
                  </button>
                  <button className="flex-1 py-2 bg-surface-container hover:bg-surface-container-highest text-on-surface text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1">
                    <MaterialIcon icon="insights" size="sm" />
                    Desempenho
                  </button>
                  <button className="p-2 bg-surface-container hover:bg-surface-container-highest text-stone-400 rounded-lg transition-all">
                    <MaterialIcon icon="more_vert" size="sm" />
                  </button>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* ── Credenciais & Performance Tab ── */
        <div className="space-y-6">
          <DataTable
            columns={credenciaisColumns}
            data={credenciaisData}
            emptyMessage="Nenhum medico encontrado."
          />

          {/* Performance Benchmarks + Pending Credentials */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Performance Benchmarks */}
            <Card variant="glass" padding="md">
              <h5 className="font-headline font-bold text-on-surface mb-6 flex items-center gap-2">
                <MaterialIcon icon="monitoring" className="text-primary-container" />
                Benchmarks de Performance
              </h5>
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <MaterialIcon icon="analytics" size="xl" className="text-stone-600 mb-3" />
                <p className="text-sm text-stone-400">
                  Benchmarks serao calculados com base nos dados reais de atendimento.
                </p>
              </div>
            </Card>

            {/* Pending Credentials */}
            <Card variant="glass" padding="md" className="bg-primary-container/5">
              <h5 className="font-headline font-bold text-on-surface mb-6 flex items-center gap-2">
                <MaterialIcon icon="notifications_active" className="text-primary-container" />
                Credenciais Pendentes
              </h5>
              <div className="space-y-4">
                {doctors
                  .filter((d) => !d.crmVerificado || d.documentosPendentes > 0)
                  .map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-3 rounded-lg border border-white/5 bg-surface-container/40"
                    >
                      <div className="flex items-center gap-3">
                        <MaterialIcon
                          icon={doc.crmVerificado ? "task" : "warning"}
                          className={doc.crmVerificado ? "text-primary-container" : "text-error"}
                        />
                        <div>
                          <p className="text-xs font-bold text-on-surface">{doc.nome}</p>
                          <p className="text-[10px] text-stone-500">
                            {!doc.crmVerificado
                              ? "CRM aguardando validacao"
                              : `${doc.documentosPendentes} documento(s) pendente(s)`}
                          </p>
                        </div>
                      </div>
                      <button className="text-[10px] font-bold uppercase tracking-widest text-primary hover:underline">
                        {doc.crmVerificado ? "Revisar" : "Validar"}
                      </button>
                    </div>
                  ))}

                {doctors.filter((d) => !d.crmVerificado || d.documentosPendentes > 0).length ===
                  0 && (
                  <div className="text-center py-6">
                    <MaterialIcon icon="check_circle" size="xl" className="text-primary mb-2" />
                    <p className="text-sm text-stone-400">Todas as credenciais estao em dia.</p>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
