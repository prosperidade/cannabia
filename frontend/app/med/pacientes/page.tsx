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

type PatientSummary = {
  patient_id: number | null;
  patient_name: string;
  phone: string;
  last_attendance_date: string;
  last_status: string;
  attendance_count: number;
};

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

function normaliseStatus(status: string): string {
  return status.toLowerCase().replace(/\s+/g, "_").replace(/ã/g, "a").replace(/ç/g, "c");
}

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

/* -------------------------------------------------------------------------- */

export default function PacientesPage() {
  const router = useRouter();
  const session = useApiSession();

  const [attendances, setAttendances] = useState<AttendanceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!session.loading && !session.data?.authenticated) {
      router.replace("/login");
    }
  }, [session.loading, session.data, router]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Sprint 3 Page-Migration: envelope `Paginated<AttendanceListItem>`.
      const env = await listAttendances({ limit: 200 });
      setAttendances(env.items);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Falha ao carregar pacientes.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session.data?.authenticated) {
      void fetchData();
    }
  }, [session.data?.authenticated, fetchData]);

  /** Extract unique patients from attendances, picking latest attendance info. */
  const patients = useMemo(() => {
    const map = new Map<string, PatientSummary>();

    for (const a of attendances) {
      const key = a.patient_id != null ? `id:${a.patient_id}` : `phone:${a.phone}`;
      const existing = map.get(key);

      if (
        !existing ||
        new Date(a.created_at).getTime() > new Date(existing.last_attendance_date).getTime()
      ) {
        map.set(key, {
          patient_id: a.patient_id,
          patient_name: a.patient_name,
          phone: a.phone,
          last_attendance_date: a.created_at,
          last_status: a.status,
          attendance_count: (existing?.attendance_count ?? 0) + 1,
        });
      } else {
        existing.attendance_count += 1;
      }
    }

    return Array.from(map.values()).sort(
      (a, b) =>
        new Date(b.last_attendance_date).getTime() - new Date(a.last_attendance_date).getTime(),
    );
  }, [attendances]);

  const filtered = useMemo(() => {
    if (!search.trim()) return patients;
    const q = search.trim().toLowerCase();
    return patients.filter(
      (p) => p.patient_name.toLowerCase().includes(q) || p.phone.toLowerCase().includes(q),
    );
  }, [patients, search]);

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
          Meus Pacientes
        </h1>
        <p className="text-stone-500 text-sm flex items-center gap-2">
          <MaterialIcon icon="group" size="sm" className="text-primary" />
          {patients.length} paciente{patients.length !== 1 ? "s" : ""} registrado
          {patients.length !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Search */}
      <SearchBar
        value={search}
        onChange={setSearch}
        placeholder="Buscar por nome ou telefone..."
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
          <Button variant="secondary" size="sm" icon="refresh" onClick={fetchData}>
            Tentar novamente
          </Button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel rounded-2xl p-12 text-center space-y-4 border border-white/5">
          <div className="w-20 h-20 mx-auto rounded-full bg-surface-container-high flex items-center justify-center">
            <MaterialIcon icon="group" size="xl" className="text-stone-600" />
          </div>
          <h3 className="text-lg font-headline font-bold text-stone-400">
            Nenhum paciente encontrado
          </h3>
          <p className="text-sm text-stone-600 max-w-md mx-auto">
            Seus pacientes aparecerao aqui conforme forem atendidos pelo sistema.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((p, idx) => {
            const normStatus = normaliseStatus(p.last_status);
            const statusCfg = STATUS_BADGE[normStatus] ?? {
              label: p.last_status,
              tone: "neutral" as const,
            };
            const href =
              p.patient_id != null
                ? `/med/prontuario/${p.patient_id}`
                : `/med/prontuario/${encodeURIComponent(p.phone)}`;

            return (
              <Link key={p.patient_id ?? `p-${idx}`} href={href} className="block">
                <div
                  className={cn(
                    "glass-panel rounded-2xl p-5 transition-colors border border-white/5",
                    "hover:bg-surface-container cursor-pointer",
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-full bg-primary-container/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
                      {getInitials(p.patient_name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-bold text-on-surface truncate">{p.patient_name}</h3>
                      <p className="text-xs text-stone-500 font-mono mt-0.5">{p.phone}</p>
                      <div className="flex flex-wrap items-center gap-2 mt-3">
                        <Badge tone={statusCfg.tone} className="text-[9px]">
                          {statusCfg.label}
                        </Badge>
                        <span className="text-[10px] text-stone-500 flex items-center gap-1">
                          <MaterialIcon icon="calendar_today" size="sm" className="text-[11px]" />
                          {formatDate(p.last_attendance_date)}
                        </span>
                        <span className="text-[10px] text-stone-500">
                          {p.attendance_count} atendimento
                          {p.attendance_count !== 1 ? "s" : ""}
                        </span>
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
