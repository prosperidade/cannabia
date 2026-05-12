"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

import {
  Button,
  Badge,
  Card,
  MaterialIcon,
  StatCard,
  Input,
} from "@/components/ui-tw";
import { cn } from "@/lib/cn";
import { useApiSession } from "@/lib/use-api-session";
import { ApiError, listAppointments, createAppointment, createAppointmentTriageLink } from "@/lib/api";
import type { AppointmentItem } from "@/lib/types";

/* ── helpers ───────────────────────────────────────────────────────── */

const WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sab"] as const;

function fmtDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function isToday(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function isThisWeek(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const startOfWeek = new Date(now);
  startOfWeek.setDate(now.getDate() - now.getDay());
  startOfWeek.setHours(0, 0, 0, 0);
  const endOfWeek = new Date(startOfWeek);
  endOfWeek.setDate(startOfWeek.getDate() + 7);
  return d >= startOfWeek && d < endOfWeek;
}

function groupByDate(items: AppointmentItem[]) {
  const groups: Record<string, AppointmentItem[]> = {};
  for (const item of items) {
    const key = new Date(item.appointment_date).toISOString().slice(0, 10);
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
}

const statusBadge: Record<string, { tone: "primary" | "success" | "warning" | "danger" | "neutral"; label: string }> = {
  confirmed: { tone: "success", label: "Confirmado" },
  pending: { tone: "warning", label: "Pendente" },
  cancelled: { tone: "danger", label: "Cancelado" },
  completed: { tone: "primary", label: "Concluido" },
};

const typeBadge: Record<string, { icon: string; label: string }> = {
  presencial: { icon: "location_on", label: "Presencial" },
  online: { icon: "videocam", label: "Online" },
};

/* ── doctors mock (used in filters & form) ─────────────────────────── */
const DOCTORS = [
  "Todos os Medicos",
  "Dr. Aris Thorne",
  "Dra. Elena Vance",
  "Dra. Helena Freitas",
];

/* ── mini calendar ─────────────────────────────────────────────────── */
function MiniCalendar({
  appointments,
  selectedDate,
  onSelect,
}: {
  appointments: AppointmentItem[];
  selectedDate: string | null;
  onSelect: (d: string) => void;
}) {
  const [offset, setOffset] = useState(0);

  const ref = new Date();
  ref.setMonth(ref.getMonth() + offset);
  const year = ref.getFullYear();
  const month = ref.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();

  const monthLabel = new Date(year, month).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });

  // count appointments per day
  const countByDay: Record<number, number> = {};
  for (const a of appointments) {
    const d = new Date(a.appointment_date);
    if (d.getFullYear() === year && d.getMonth() === month) {
      countByDay[d.getDate()] = (countByDay[d.getDate()] || 0) + 1;
    }
  }

  const cells: { day: number; current: boolean; key: string }[] = [];
  for (let i = firstDay - 1; i >= 0; i--) {
    cells.push({ day: daysInPrev - i, current: false, key: `prev-${i}` });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, current: true, key: `cur-${d}` });
  }
  const remaining = 7 - (cells.length % 7);
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) {
      cells.push({ day: i, current: false, key: `next-${i}` });
    }
  }

  const todayDate = new Date();
  const todayStr =
    todayDate.getFullYear() === year && todayDate.getMonth() === month
      ? todayDate.getDate()
      : -1;

  return (
    <Card className="overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold font-headline capitalize">
            {monthLabel}
          </h2>
          <div className="flex gap-1">
            <button
              onClick={() => setOffset((o) => o - 1)}
              className="p-1 hover:bg-white/5 rounded-md transition-colors"
            >
              <MaterialIcon icon="chevron_left" />
            </button>
            <button
              onClick={() => setOffset((o) => o + 1)}
              className="p-1 hover:bg-white/5 rounded-md transition-colors"
            >
              <MaterialIcon icon="chevron_right" />
            </button>
          </div>
        </div>
        <div className="flex gap-4 text-xs font-medium uppercase tracking-widest text-stone-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary" /> Consultas
          </span>
        </div>
      </div>

      {/* header */}
      <div className="grid grid-cols-7 gap-px rounded-t-2xl overflow-hidden border border-white/5">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="bg-surface-container-high/40 p-3 text-center text-[10px] font-bold text-stone-500 uppercase"
          >
            {d}
          </div>
        ))}
        {cells.map((cell) => {
          const isoStr =
            cell.current
              ? `${year}-${String(month + 1).padStart(2, "0")}-${String(cell.day).padStart(2, "0")}`
              : "";
          const isSelected = selectedDate === isoStr;
          const count = cell.current ? countByDay[cell.day] || 0 : 0;

          return (
            <div
              key={cell.key}
              onClick={cell.current ? () => onSelect(isoStr) : undefined}
              className={cn(
                "p-3 min-h-[80px] lg:min-h-[90px] flex flex-col transition-colors",
                !cell.current && "opacity-30 text-stone-700",
                cell.current && "text-on-surface cursor-pointer hover:bg-white/5",
                isSelected && "bg-primary/10 border-2 border-primary/30",
                cell.day === todayStr && cell.current && !isSelected && "bg-white/5",
              )}
            >
              <span
                className={cn(
                  "text-sm",
                  cell.day === todayStr && cell.current && "text-primary font-bold",
                )}
              >
                {cell.day}
              </span>
              {count > 0 && (
                <div className="mt-auto bg-primary/20 text-primary text-[10px] p-1 rounded-md border border-primary/20 text-center">
                  {count} Consulta{count > 1 ? "s" : ""}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ── new appointment modal ─────────────────────────────────────────── */
function NewAppointmentModal({
  open,
  onClose,
  onCreated,
  csrfToken,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
  csrfToken: string;
}) {
  const [patientName, setPatientName] = useState("");
  const [date, setDate] = useState("");
  const [doctor, setDoctor] = useState("");
  const [appointmentType, setAppointmentType] = useState<"presencial" | "online">("presencial");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!patientName.trim() || !date) {
      setFormError("Preencha todos os campos obrigatorios.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      await createAppointment(csrfToken, {
        patient_name: patientName.trim(),
        appointment_date: new Date(date).toISOString(),
      });
      onCreated();
      onClose();
      setPatientName("");
      setDate("");
      setDoctor("");
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Falha ao criar agendamento.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <Card className="w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-stone-400 hover:text-white transition-colors"
        >
          <MaterialIcon icon="close" />
        </button>
        <h3 className="text-xl font-bold font-headline mb-6">
          Novo Agendamento
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nome do Paciente"
            icon="person"
            value={patientName}
            onChange={(e) => setPatientName(e.target.value)}
            placeholder="Nome completo"
          />
          <Input
            label="Data e Hora"
            icon="calendar_today"
            type="datetime-local"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Medico
            </label>
            <select
              value={doctor}
              onChange={(e) => setDoctor(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant/30 rounded-DEFAULT px-4 py-3 text-on-surface focus:border-primary-container focus:outline-none transition-colors"
            >
              <option value="">Selecionar medico...</option>
              {DOCTORS.slice(1).map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[10px] uppercase tracking-widest text-stone-400 font-bold">
              Tipo
            </label>
            <div className="flex gap-3">
              {(["presencial", "online"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setAppointmentType(t)}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-colors",
                    appointmentType === t
                      ? "border-primary/30 bg-primary/10 text-primary"
                      : "border-outline-variant/30 text-stone-400 hover:bg-white/5",
                  )}
                >
                  <MaterialIcon
                    icon={t === "presencial" ? "location_on" : "videocam"}
                    size="sm"
                  />
                  {t === "presencial" ? "Presencial" : "Online"}
                </button>
              ))}
            </div>
          </div>
          {formError && (
            <p className="text-sm text-error">{formError}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" type="button" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              icon="add_circle"
              loading={saving}
            >
              Criar Agendamento
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ── page ───────────────────────────────────────────────────────────── */
export default function AgendamentosPage() {
  const router = useRouter();
  const session = useApiSession();
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDoctor, setFilterDoctor] = useState("Todos os Medicos");
  const [filterStatus, setFilterStatus] = useState("all");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [linkLoading, setLinkLoading] = useState<number | null>(null);
  const [copiedLink, setCopiedLink] = useState<number | null>(null);

  async function handleGenerateLink(appointmentId: number) {
    const csrf = session.data?.csrf_token ?? "";
    setLinkLoading(appointmentId);
    try {
      const result = await createAppointmentTriageLink(appointmentId, csrf);
      await navigator.clipboard.writeText(result.url);
      setCopiedLink(appointmentId);
      setTimeout(() => setCopiedLink(null), 3000);
    } catch (err) {
      alert(err instanceof ApiError ? err.message : "Falha ao gerar link de triagem.");
    } finally {
      setLinkLoading(null);
    }
  }

  const fetchAppointments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Sprint 3 Page-Migration: envelope `Paginated<AppointmentItem>`.
      const env = await listAppointments({ limit: 200 });
      setAppointments(env.items);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Falha ao carregar agendamentos.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (session.loading) return;
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }
    void fetchAppointments();
  }, [session.loading, session.data, router, fetchAppointments]);

  /* stats */
  const total = appointments.length;
  const today = appointments.filter((a) => isToday(a.appointment_date)).length;
  const thisWeek = appointments.filter((a) =>
    isThisWeek(a.appointment_date),
  ).length;
  const cancelled = appointments.filter(
    (a) => a.status === "cancelled",
  ).length;

  /* filtered */
  const filtered = appointments.filter((a) => {
    if (filterStatus !== "all" && a.status !== filterStatus) return false;
    if (
      selectedDate &&
      !a.appointment_date.startsWith(selectedDate)
    )
      return false;
    return true;
  });

  const grouped = groupByDate(filtered);

  if (session.loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <h1 className="text-3xl md:text-4xl font-extrabold font-headline tracking-tighter text-white mb-2">
            Gestao de Agendamentos
          </h1>
          <p className="text-on-surface-variant max-w-xl text-sm">
            Visualize e organize o fluxo clinico com precisao assistida por IA.
            Identifique conflitos e otimize a ocupacao das salas.
          </p>
        </div>
        <Button
          icon="add_circle"
          onClick={() => setShowModal(true)}
          className="rounded-full shadow-lg shadow-primary/20"
        >
          Novo Agendamento
        </Button>
      </div>

      {/* stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon="calendar_month"
          label="Total Agendamentos"
          value={total}
        />
        <StatCard
          icon="today"
          label="Hoje"
          value={today}
          delta={today > 0 ? `${today} consultas` : undefined}
          deltaType="up"
        />
        <StatCard
          icon="date_range"
          label="Esta Semana"
          value={thisWeek}
        />
        <StatCard
          icon="cancel"
          label="Cancelados"
          value={cancelled}
          deltaType={cancelled > 0 ? "down" : "neutral"}
        />
      </div>

      {/* filters */}
      <div className="flex flex-wrap gap-3">
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-3">
          <MaterialIcon icon="medication" size="sm" className="text-primary" />
          <select
            value={filterDoctor}
            onChange={(e) => setFilterDoctor(e.target.value)}
            className="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer"
          >
            {DOCTORS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <div className="glass-panel px-4 py-2 rounded-full flex items-center gap-3">
          <MaterialIcon icon="filter_list" size="sm" className="text-primary" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-transparent border-none text-sm text-on-surface focus:ring-0 cursor-pointer"
          >
            <option value="all">Todos os Status</option>
            <option value="confirmed">Confirmado</option>
            <option value="pending">Pendente</option>
            <option value="cancelled">Cancelado</option>
            <option value="completed">Concluido</option>
          </select>
        </div>
        {selectedDate && (
          <button
            onClick={() => setSelectedDate(null)}
            className="glass-panel px-4 py-2 rounded-full flex items-center gap-2 text-sm text-primary hover:bg-white/5 transition-colors"
          >
            <MaterialIcon icon="close" size="sm" />
            Limpar filtro de data
          </button>
        )}
      </div>

      {/* main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* calendar */}
        <div className="lg:col-span-8">
          <MiniCalendar
            appointments={appointments}
            selectedDate={selectedDate}
            onSelect={(d) =>
              setSelectedDate((prev) => (prev === d ? null : d))
            }
          />
        </div>

        {/* sidebar: upcoming */}
        <div className="lg:col-span-4 space-y-6">
          <Card className="h-fit">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-bold text-xl font-headline tracking-tight">
                Proximas Consultas
              </h3>
              <Badge tone="neutral">Hoje</Badge>
            </div>

            {loading ? (
              <div className="flex justify-center py-8">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              </div>
            ) : error ? (
              <p className="text-sm text-error py-4">{error}</p>
            ) : (
              <div className="space-y-3">
                {appointments
                  .filter((a) => new Date(a.appointment_date) >= new Date())
                  .sort(
                    (a, b) =>
                      new Date(a.appointment_date).getTime() -
                      new Date(b.appointment_date).getTime(),
                  )
                  .slice(0, 5)
                  .map((appt) => {
                    const sb = statusBadge[appt.status] ?? statusBadge.pending;
                    return (
                      <div
                        key={appt.id}
                        className="group p-4 rounded-2xl hover:bg-white/5 transition-all cursor-pointer border border-transparent hover:border-white/5"
                      >
                        <div className="flex items-start justify-between mb-1">
                          <div>
                            <p className="font-bold text-sm text-white">
                              {appt.patient_name}
                            </p>
                            <p className="text-[10px] text-stone-500 uppercase tracking-widest">
                              {isToday(appt.appointment_date)
                                ? "Hoje"
                                : fmtDate(appt.appointment_date)}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-primary font-bold text-sm">
                              {fmtTime(appt.appointment_date)}
                            </p>
                            <Badge tone={sb.tone}>{sb.label}</Badge>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                {appointments.filter(
                  (a) => new Date(a.appointment_date) >= new Date(),
                ).length === 0 && (
                  <p className="text-sm text-stone-500 text-center py-4">
                    Nenhuma consulta futura encontrada.
                  </p>
                )}
              </div>
            )}
          </Card>

          {/* AI Insight card */}
          <Card className="bg-gradient-to-tr from-primary/5 to-transparent">
            <div className="flex items-center gap-3 mb-4">
              <MaterialIcon
                icon="auto_awesome"
                className="text-primary"
              />
              <h4 className="font-bold text-sm uppercase tracking-widest text-primary">
                Analise Inteligente
              </h4>
            </div>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              A taxa de ocupacao esta em{" "}
              <span className="text-primary font-bold">
                {total > 0 ? Math.min(Math.round((thisWeek / 40) * 100), 100) : 0}%
              </span>{" "}
              para as proximas 48h. Recomendamos monitorar horarios de pico para
              otimizar o fluxo de atendimento.
            </p>
          </Card>
        </div>
      </div>

      {/* grouped appointments list */}
      {grouped.length > 0 && (
        <div className="space-y-6">
          <h3 className="text-xl font-bold font-headline">
            Agendamentos{" "}
            {selectedDate
              ? `- ${fmtDate(selectedDate + "T00:00:00")}`
              : ""}
          </h3>
          {grouped.map(([dateKey, items]) => (
            <div key={dateKey}>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs font-bold text-primary uppercase tracking-widest">
                  {fmtDate(dateKey + "T00:00:00")}
                </span>
                <div className="flex-1 h-px bg-white/5" />
                <Badge tone="neutral">{items.length} agendamento{items.length > 1 ? "s" : ""}</Badge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {items
                  .sort(
                    (a, b) =>
                      new Date(a.appointment_date).getTime() -
                      new Date(b.appointment_date).getTime(),
                  )
                  .map((appt) => {
                    const sb = statusBadge[appt.status] ?? statusBadge.pending;
                    return (
                      <Card
                        key={appt.id}
                        padding="sm"
                        className="flex items-center justify-between group hover:border-white/10 transition-all"
                      >
                        <div className="flex items-center gap-4">
                          <div className="flex flex-col items-center justify-center border-r border-stone-800/50 pr-4">
                            <span className="text-xs font-bold text-primary">
                              {fmtTime(appt.appointment_date)}
                            </span>
                          </div>
                          <div>
                            <p className="font-bold text-sm text-on-surface font-headline">
                              {appt.patient_name}
                            </p>
                            <p className="text-xs text-stone-500">
                              Cod. {appt.id}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleGenerateLink(appt.id)}
                            disabled={linkLoading === appt.id}
                            title="Gerar link de triagem para este paciente"
                            className={cn(
                              "p-2 rounded-lg border transition-all text-xs font-medium flex items-center gap-1.5",
                              copiedLink === appt.id
                                ? "border-success/30 bg-success/10 text-success"
                                : "border-outline-variant/30 text-stone-400 hover:bg-primary/10 hover:text-primary hover:border-primary/30",
                            )}
                          >
                            {linkLoading === appt.id ? (
                              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                            ) : (
                              <MaterialIcon
                                icon={copiedLink === appt.id ? "check" : "link"}
                                size="sm"
                              />
                            )}
                            {copiedLink === appt.id ? "Copiado" : "Triagem"}
                          </button>
                          <div className="flex flex-col items-end gap-1">
                            <Badge tone={sb.tone}>{sb.label}</Badge>
                          </div>
                        </div>
                      </Card>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <Card className="text-center py-12">
          <MaterialIcon
            icon="event_busy"
            size="xl"
            className="text-stone-600 mx-auto mb-4"
          />
          <p className="text-stone-400">
            Nenhum agendamento encontrado com os filtros atuais.
          </p>
        </Card>
      )}

      {/* modal */}
      <NewAppointmentModal
        open={showModal}
        onClose={() => setShowModal(false)}
        onCreated={fetchAppointments}
        csrfToken={session.data?.csrf_token ?? ""}
      />
    </div>
  );
}
