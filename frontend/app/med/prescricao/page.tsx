"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { cn } from "@/lib/cn";
import { listPrescriptions, ApiError } from "@/lib/api";
import { useApiSession } from "@/lib/use-api-session";
import {
  MaterialIcon,
  Badge,
  Button,
  SearchBar,
} from "@/components/ui-tw";

/* -------------------------------------------------------------------------- */

type PrescriptionItem = {
  id?: number;
  patient_name?: string;
  status?: string;
  dosage?: string;
  created_at?: string;
  [key: string]: unknown;
};

function formatDate(dateStr?: string): string {
  if (!dateStr) return "--";
  const d = new Date(dateStr);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getInitials(name?: string): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0][0]?.toUpperCase() ?? "?";
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const STATUS_BADGE: Record<
  string,
  { label: string; tone: "primary" | "success" | "warning" | "danger" | "neutral" }
> = {
  ativa: { label: "Ativa", tone: "success" },
  emitida: { label: "Emitida", tone: "primary" },
  pendente: { label: "Pendente", tone: "warning" },
  cancelada: { label: "Cancelada", tone: "danger" },
  rascunho: { label: "Rascunho", tone: "neutral" },
};

/* -------------------------------------------------------------------------- */

export default function PrescricoesPage() {
  const router = useRouter();
  const session = useApiSession();

  const [prescriptions, setPrescriptions] = useState<PrescriptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      router.replace("/login");
    }
  }, [session.loading, session.data, router]);

  const fetchPrescriptions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await listPrescriptions();
      setPrescriptions((resp.data ?? []) as PrescriptionItem[]);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setPrescriptions([]);
      } else {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Falha ao carregar prescricoes.";
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session.data?.authenticated) {
      void fetchPrescriptions();
    }
  }, [session.data?.authenticated, fetchPrescriptions]);

  const filtered = prescriptions.filter((p) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (p.patient_name ?? "").toLowerCase().includes(q);
  });

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
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl lg:text-3xl font-headline font-bold text-on-surface leading-tight">
            Prescricoes
          </h1>
          <p className="text-stone-500 text-sm flex items-center gap-2">
            <MaterialIcon
              icon="prescriptions"
              size="sm"
              className="text-primary"
            />
            Gerencie as prescricoes dos pacientes
          </p>
        </div>
        <Link href="/med/prescricao/nova">
          <Button icon="add" size="sm">
            Nova Prescricao
          </Button>
        </Link>
      </div>

      {/* Search */}
      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar por nome do paciente..."
        className="lg:max-w-sm"
      />

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
            onClick={fetchPrescriptions}
          >
            Tentar novamente
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center space-y-4 border border-white/5">
          <div className="w-20 h-20 mx-auto rounded-full bg-surface-container-high flex items-center justify-center">
            <MaterialIcon
              icon="prescriptions"
              size="xl"
              className="text-stone-600"
            />
          </div>
          <h3 className="text-lg font-headline font-bold text-stone-400">
            Nenhuma prescricao encontrada
          </h3>
          <p className="text-sm text-stone-600 max-w-md mx-auto">
            As prescricoes aparecerao aqui conforme forem emitidas. Clique em
            &quot;Nova Prescricao&quot; para criar uma.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((item, idx) => {
            const key = item.id ?? idx;
            const status = (
              (item.status ?? "pendente") as string
            ).toLowerCase();
            const statusCfg = STATUS_BADGE[status] ?? {
              label: status,
              tone: "neutral" as const,
            };
            return (
              <Link
                key={key}
                href={`/med/prescricao/${item.id ?? idx}`}
                className="block"
              >
                <div
                  className={cn(
                    "glass-panel rounded-2xl p-4 lg:p-6 transition-colors",
                    "hover:bg-surface-container cursor-pointer border border-white/5",
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
                      {getInitials(item.patient_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-bold text-on-surface truncate">
                          {item.patient_name ?? "Paciente"}
                        </h3>
                        <Badge tone={statusCfg.tone} className="shrink-0">
                          {statusCfg.label}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-stone-500">
                        <span className="flex items-center gap-1">
                          <MaterialIcon
                            icon="calendar_today"
                            size="sm"
                            className="text-[12px]"
                          />
                          {formatDate(item.created_at as string | undefined)}
                        </span>
                        {item.dosage && (
                          <span className="flex items-center gap-1 font-mono">
                            <MaterialIcon
                              icon="medication"
                              size="sm"
                              className="text-[12px]"
                            />
                            {String(item.dosage)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Bottom padding for mobile nav */}
      <div className="h-20 lg:h-0" />
    </div>
  );
}
