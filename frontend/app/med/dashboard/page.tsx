"use client";

import { useEffect, useMemo, useState } from "react";

import { Card, MaterialIcon, Badge, Button, StatCard, Avatar } from "@/components/ui-tw";
import { listAppointments, listReturns } from "@/lib/api";
import type { AppointmentItem } from "@/lib/types";
import { useApiSession } from "@/lib/use-api-session";

/**
 * /med/dashboard — home do medico assalariado puro (sem is_clinic_admin).
 *
 * Foco: o que o medico precisa ver ao chegar no app:
 *   1) Fila do dia      — agendamentos com horario para hoje
 *   2) Retornos pendentes — pacientes em tratamento sem proxima consulta
 *
 * Medico-dono (is_clinic_admin=true) cai em /org/dashboard, que e o
 * painel gerencial com KPIs do tenant.
 */
type PendingReturn = {
  treatment_plan_id?: number;
  patient_id?: number;
  patient_name?: string;
  plan_name?: string;
  treatment_status?: string;
  next_return_date?: string | null;
};

export default function MedDashboardPage() {
  const { data: session } = useApiSession();
  const userName = session?.user?.username ?? "";

  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [returns, setReturns] = useState<PendingReturn[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErrorMsg(null);

    Promise.all([listAppointments({ limit: 200 }), listReturns()])
      .then(([appts, retsRaw]) => {
        if (!alive) return;
        // Sprint 3 Page-Migration: envelope `Paginated<AppointmentItem>`.
        const items = appts?.items ?? [];
        setAppointments(items as AppointmentItem[]);
        // /returns retorna lista, mas api.ts tipa como Record. Cast via unknown.
        const retsArr = retsRaw.data as unknown as PendingReturn[] | undefined;
        setReturns(Array.isArray(retsArr) ? retsArr : []);
      })
      .catch((err) => {
        if (!alive) return;
        const msg = err instanceof Error ? err.message : "Falha ao carregar a fila do dia.";
        setErrorMsg(msg);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // --- Derivacoes locais (filtragem por hoje + ordenacao) -----------------
  const todayPrefix = new Date().toISOString().slice(0, 10); // YYYY-MM-DD

  const todayAppointments = useMemo(() => {
    return appointments
      .filter((a) =>
        typeof a.appointment_date === "string" ? a.appointment_date.startsWith(todayPrefix) : false,
      )
      .sort((a, b) => a.appointment_date.localeCompare(b.appointment_date));
  }, [appointments, todayPrefix]);

  const inQueueCount = useMemo(() => {
    const open = new Set(["agendado", "confirmado", "pending", "scheduled"]);
    return todayAppointments.filter((a) => open.has((a.status ?? "").toLowerCase())).length;
  }, [todayAppointments]);

  const completedTodayCount = useMemo(() => {
    const done = new Set(["atendido", "completed", "finalizado", "concluido"]);
    return todayAppointments.filter((a) => done.has((a.status ?? "").toLowerCase())).length;
  }, [todayAppointments]);

  const pendingReturns = useMemo(() => {
    return returns.filter((r) => (r.treatment_status ?? "").toLowerCase() !== "completed");
  }, [returns]);

  const todayLabel = useMemo(() => {
    return new Date().toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
    });
  }, []);

  return (
    <section className="p-4 md:p-8 space-y-6 pb-28 md:pb-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <h2 className="text-2xl md:text-3xl font-extrabold font-headline tracking-tight text-on-surface">
            {userName ? `Ola, ${userName}` : "Bom dia, doutor(a)"}
          </h2>
          <p className="text-sm text-stone-500 capitalize">{todayLabel}</p>
        </div>
        <div className="flex gap-2">
          <a href="/med/retornos">
            <Button variant="secondary" size="sm" icon="event_repeat">
              Retornos
            </Button>
          </a>
          <a href="/med/fila">
            <Button size="sm" icon="queue">
              Abrir fila
            </Button>
          </a>
        </div>
      </div>

      {errorMsg && (
        <Card padding="md" className="border-error/40 bg-error/5">
          <div className="flex items-center gap-3 text-error">
            <MaterialIcon icon="error" />
            <p className="text-sm">Nao foi possivel carregar: {errorMsg}</p>
          </div>
        </Card>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard
          icon="queue"
          label="Em fila agora"
          value={loading ? "..." : String(inQueueCount)}
        />
        <StatCard
          icon="check_circle"
          label="Atendidos hoje"
          value={loading ? "..." : String(completedTodayCount)}
        />
        <StatCard
          icon="event_repeat"
          label="Retornos pendentes"
          value={loading ? "..." : String(pendingReturns.length)}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Fila do dia */}
        <Card variant="glass" padding="lg" className="xl:col-span-2">
          <div className="flex items-start justify-between mb-5 gap-3">
            <SectionHeader
              icon="queue"
              title="Fila do dia"
              desc={
                loading
                  ? "Carregando..."
                  : `${todayAppointments.length} agendamento${
                      todayAppointments.length === 1 ? "" : "s"
                    } para hoje`
              }
            />
            <a href="/med/fila">
              <Button variant="ghost" size="sm" icon="arrow_forward">
                Ver tudo
              </Button>
            </a>
          </div>

          {loading ? (
            <SkeletonRows count={3} />
          ) : todayAppointments.length === 0 ? (
            <EmptyState
              icon="event_busy"
              title="Sem agendamentos hoje"
              subtitle="Aproveite para revisar retornos ou estudar casos abertos."
            />
          ) : (
            <ul className="space-y-2">
              {todayAppointments.slice(0, 8).map((appt) => (
                <AppointmentRow key={appt.id} appt={appt} />
              ))}
              {todayAppointments.length > 8 && (
                <li className="pt-2 text-center text-xs text-stone-500">
                  + {todayAppointments.length - 8} agendamento
                  {todayAppointments.length - 8 === 1 ? "" : "s"} restante
                  {todayAppointments.length - 8 === 1 ? "" : "s"} —{" "}
                  <a href="/med/fila" className="text-primary font-bold hover:underline">
                    abrir fila completa
                  </a>
                </li>
              )}
            </ul>
          )}
        </Card>

        {/* Retornos pendentes */}
        <Card variant="glass" padding="lg" className="xl:col-span-1">
          <div className="flex items-start justify-between mb-5 gap-3">
            <SectionHeader
              icon="event_repeat"
              title="Retornos pendentes"
              desc={
                loading
                  ? "Carregando..."
                  : `${pendingReturns.length} paciente${
                      pendingReturns.length === 1 ? "" : "s"
                    } aguardando`
              }
            />
            <a href="/med/retornos">
              <Button variant="ghost" size="sm" icon="arrow_forward">
                Ver tudo
              </Button>
            </a>
          </div>

          {loading ? (
            <SkeletonRows count={3} />
          ) : pendingReturns.length === 0 ? (
            <EmptyState
              icon="check_circle"
              title="Sem retornos pendentes"
              subtitle="Todos os planos terapeuticos em dia."
            />
          ) : (
            <ul className="space-y-2">
              {pendingReturns.slice(0, 5).map((ret, idx) => (
                <ReturnRow key={ret.treatment_plan_id ?? ret.patient_id ?? idx} ret={ret} />
              ))}
              {pendingReturns.length > 5 && (
                <li className="pt-2 text-center text-xs text-stone-500">
                  + {pendingReturns.length - 5} paciente
                  {pendingReturns.length - 5 === 1 ? "" : "s"}
                </li>
              )}
            </ul>
          )}
        </Card>
      </div>
    </section>
  );
}

/* ── Componentes internos ─────────────────────────────────────── */

function SectionHeader({ icon, title, desc }: { icon: string; title: string; desc?: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
        <MaterialIcon icon={icon} className="text-primary" />
      </div>
      <div>
        <h3 className="text-lg font-headline font-bold text-on-surface leading-tight">{title}</h3>
        {desc && <p className="text-xs text-stone-500 mt-0.5">{desc}</p>}
      </div>
    </div>
  );
}

function EmptyState({ icon, title, subtitle }: { icon: string; title: string; subtitle: string }) {
  return (
    <div className="py-10 flex flex-col items-center justify-center text-center gap-2">
      <MaterialIcon icon={icon} size="xl" className="text-stone-600" />
      <p className="text-sm font-bold text-on-surface">{title}</p>
      <p className="text-xs text-stone-500 max-w-md">{subtitle}</p>
    </div>
  );
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <ul className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className="h-14 rounded-xl bg-surface-container-low/60 animate-pulse" />
      ))}
    </ul>
  );
}

function AppointmentRow({ appt }: { appt: AppointmentItem }) {
  const time = formatTime(appt.appointment_date);
  const statusInfo = mapStatus(appt.status);
  return (
    <li className="flex items-center gap-3 p-3 rounded-xl bg-surface-container-low border border-outline-variant/20 hover:border-primary/30 transition-colors">
      <div className="w-12 text-center flex-shrink-0">
        <p className="text-xs font-bold text-on-surface">{time}</p>
      </div>
      <Avatar name={appt.patient_name || "Paciente"} size="sm" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-on-surface truncate">
          {appt.patient_name || "Paciente"}
        </p>
        <p className="text-[11px] text-stone-500">Consulta clinica</p>
      </div>
      <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
    </li>
  );
}

function ReturnRow({ ret }: { ret: PendingReturn }) {
  const dueLabel = formatReturnDate(ret.next_return_date);
  return (
    <li className="flex items-center gap-3 p-3 rounded-xl bg-surface-container-low border border-outline-variant/20 hover:border-primary/30 transition-colors">
      <Avatar name={ret.patient_name || "Paciente"} size="sm" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-on-surface truncate">
          {ret.patient_name || "Paciente"}
        </p>
        <p className="text-[11px] text-stone-500 truncate">
          {ret.plan_name || "Plano terapeutico"}
        </p>
      </div>
      {dueLabel && <Badge tone="warning">{dueLabel}</Badge>}
    </li>
  );
}

/* ── Helpers ─────────────────────────────────────────────────── */

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "--:--";
    return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "--:--";
  }
}

function formatReturnDate(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
  } catch {
    return value;
  }
}

function mapStatus(status: string): {
  label: string;
  tone: "primary" | "success" | "warning" | "danger" | "neutral";
} {
  const s = (status ?? "").toLowerCase();
  if (["atendido", "completed", "finalizado", "concluido"].includes(s)) {
    return { label: "Atendido", tone: "success" };
  }
  if (["em_atendimento", "in_progress", "atendendo"].includes(s)) {
    return { label: "Em atendimento", tone: "primary" };
  }
  if (["cancelado", "cancelled"].includes(s)) {
    return { label: "Cancelado", tone: "danger" };
  }
  if (["agendado", "confirmado", "pending", "scheduled"].includes(s)) {
    return { label: "Aguardando", tone: "warning" };
  }
  return { label: status || "—", tone: "neutral" };
}
