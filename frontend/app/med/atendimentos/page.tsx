"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { listAttendances, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceListItem } from "@/lib/types";
import { MaterialIcon, Badge, Button, SearchBar } from "@/components/ui-tw";

/* -------------------------------------------------------------------------- */

type StatusFilter = "all" | "pendente" | "revisado";

const STATUS_BADGE: Record<
  string,
  { label: string; tone: "primary" | "success" | "warning" | "danger" | "neutral" }
> = {
  processado: { label: "Processado", tone: "success" },
  revisado: { label: "Revisado", tone: "primary" },
  pendente: { label: "Pendente", tone: "warning" },
  em_revisao: { label: "Em Revisao", tone: "neutral" },
  erro: { label: "Erro", tone: "danger" },
};

function normaliseStatus(status: string): string {
  return status.toLowerCase().replace(/\s+/g, "_").replace(/ã/g, "a").replace(/ç/g, "c");
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? "?";
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/* -------------------------------------------------------------------------- */

export default function AtendimentosPage() {
  const router = useRouter();
  const session = useApiSession();

  const [attendances, setAttendances] = useState<AttendanceListItem[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      router.replace("/login");
    }
  }, [session.loading, session.data, router]);

  // Sprint 3 Page-Migration: envelope `Paginated<AttendanceListItem>`.
  const fetchAttendances = useCallback(
    async (opts?: { append?: boolean }) => {
      setLoading(true);
      setError(null);
      try {
        const nextOffset = opts?.append ? offset : 0;
        const env = await listAttendances({ limit: 50, offset: nextOffset });
        setAttendances((prev) => (opts?.append ? [...prev, ...env.items] : env.items));
        setHasMore(env.has_more);
        setOffset(nextOffset + env.items.length);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Falha ao carregar atendimentos.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    },
    [offset],
  );

  const loadMore = useCallback(() => {
    void fetchAttendances({ append: true });
  }, [fetchAttendances]);

  useEffect(() => {
    if (session.data?.authenticated) {
      void fetchAttendances();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.data?.authenticated]);

  const filtered = useMemo(() => {
    let items = [...attendances];

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      items = items.filter((a) => a.patient_name.toLowerCase().includes(q));
    }

    if (statusFilter !== "all") {
      items = items.filter((a) => normaliseStatus(a.status) === statusFilter);
    }

    items.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    return items;
  }, [attendances, search, statusFilter]);

  if (session.loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6 lg:space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl lg:text-3xl font-headline font-bold text-on-surface leading-tight">
          Gestao de Atendimentos
        </h1>
        <p className="text-stone-500 text-sm flex items-center gap-2">
          <MaterialIcon icon="assignment" size="sm" className="text-primary" />
          Todos os atendimentos realizados
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:gap-4">
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Buscar por nome do paciente..."
          className="flex-1 lg:max-w-sm"
        />

        <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0 -mx-1 px-1 no-scrollbar">
          {(
            [
              { value: "all", label: "Todos" },
              { value: "pendente", label: "Pendente" },
              { value: "revisado", label: "Revisado" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={cn(
                "px-4 py-2 rounded-full text-xs font-semibold whitespace-nowrap transition-colors shrink-0",
                statusFilter === opt.value
                  ? "bg-primary text-on-primary shadow-md shadow-primary/20"
                  : "bg-surface-container-highest text-on-surface-variant hover:bg-surface-container-high",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : error ? (
        <div className="glass-panel rounded-2xl p-8 text-center space-y-4">
          <MaterialIcon icon="error_outline" size="xl" className="text-error" />
          <p className="text-stone-400">{error}</p>
          <Button
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={() => void fetchAttendances()}
          >
            Tentar novamente
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center space-y-4 border border-white/5">
          <div className="w-20 h-20 mx-auto rounded-full bg-surface-container-high flex items-center justify-center">
            <MaterialIcon icon="assignment" size="xl" className="text-stone-600" />
          </div>
          <h3 className="text-lg font-headline font-bold text-stone-400">
            Nenhum atendimento encontrado
          </h3>
          <p className="text-sm text-stone-600 max-w-md mx-auto">
            Os atendimentos aparecerao aqui conforme forem processados pelo sistema.
          </p>
        </div>
      ) : (
        <div className="glass-panel rounded-2xl overflow-hidden shadow-2xl">
          {/* Desktop table */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-high/50 border-b border-white/5">
                  <th className="px-6 py-5 text-xs font-bold text-stone-500 uppercase tracking-wider">
                    Paciente
                  </th>
                  <th className="px-6 py-5 text-xs font-bold text-stone-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-5 text-xs font-bold text-stone-500 uppercase tracking-wider">
                    Data
                  </th>
                  <th className="px-6 py-5 text-xs font-bold text-stone-500 uppercase tracking-wider">
                    Modelo
                  </th>
                  <th className="px-6 py-5 text-xs font-bold text-stone-500 uppercase tracking-wider text-right">
                    Acoes
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filtered.map((item) => {
                  const normStatus = normaliseStatus(item.status);
                  const statusCfg = STATUS_BADGE[normStatus] ?? {
                    label: item.status,
                    tone: "neutral" as const,
                  };
                  return (
                    <tr key={item.id} className="hover:bg-white/5 transition-colors group">
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-bold text-sm">
                            {getInitials(item.patient_name)}
                          </div>
                          <div>
                            <p className="font-bold text-on-surface text-sm">{item.patient_name}</p>
                            <p className="text-xs text-stone-500 font-mono">{item.phone}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <Badge tone={statusCfg.tone}>{statusCfg.label}</Badge>
                      </td>
                      <td className="px-6 py-5 text-sm text-on-surface-variant font-medium">
                        {formatDate(item.created_at)}
                      </td>
                      <td className="px-6 py-5 text-sm text-stone-500 font-mono">
                        {item.report_model}
                      </td>
                      <td className="px-6 py-5 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Link href={`/med/consulta/${item.id}`}>
                            <Button size="sm" icon="visibility" variant="secondary">
                              Ver
                            </Button>
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="lg:hidden divide-y divide-white/5">
            {filtered.map((item) => {
              const normStatus = normaliseStatus(item.status);
              const statusCfg = STATUS_BADGE[normStatus] ?? {
                label: item.status,
                tone: "neutral" as const,
              };
              return (
                <Link
                  key={item.id}
                  href={`/med/consulta/${item.id}`}
                  className="block p-4 hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-bold text-xs shrink-0">
                      {getInitials(item.patient_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="font-bold text-sm text-on-surface truncate">
                          {item.patient_name}
                        </h4>
                        <Badge tone={statusCfg.tone} className="text-[9px] shrink-0">
                          {statusCfg.label}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-stone-500">
                        <span>{formatDate(item.created_at)}</span>
                        <span className="font-mono">{item.report_model}</span>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {!loading && !error && hasMore ? (
        <div className="flex justify-center pt-2">
          <Button variant="secondary" size="sm" icon="expand_more" onClick={loadMore}>
            Carregar mais
          </Button>
        </div>
      ) : null}

      {/* Bottom padding for mobile nav */}
      <div className="h-20 lg:h-0" />
    </div>
  );
}
