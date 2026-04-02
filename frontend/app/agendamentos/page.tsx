"use client";

import { useRouter } from "next/navigation";
import { startTransition, type FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { StatusPill } from "@/components/status-pill";
import { ApiError, createAppointment, listAppointments } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { AppointmentItem } from "@/lib/types";

function statusTone(status: string) {
  const normalized = status.toLowerCase();
  if (normalized.includes("agend")) return "ok" as const;
  if (normalized.includes("cancel")) return "danger" as const;
  return "info" as const;
}

function toIsoDateTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error("Data invalida. Use a selecao de data e hora do formulario.");
  }
  return parsed.toISOString();
}

export default function AppointmentsPage() {
  const router = useRouter();
  const session = useApiSession();
  const [appointments, setAppointments] = useState<AppointmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    patient_name: "",
    appointment_date: "",
  });

  async function loadAppointments() {
    setLoading(true);
    setError(null);
    try {
      const data = await listAppointments();
      setAppointments(data);
    } catch (loadError) {
      setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar agendamentos.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }
    void loadAppointments();
  }, [router, session.data, session.loading]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session.data) {
      return;
    }

    setBusy(true);
    setError(null);
    setSaveMessage(null);

    try {
      await createAppointment(session.data.csrf_token, {
        patient_name: form.patient_name.trim(),
        appointment_date: toIsoDateTime(form.appointment_date),
      });
      setSaveMessage("Agendamento criado e integrado ao historico do paciente.");
      setForm({
        patient_name: "",
        appointment_date: "",
      });
      await loadAppointments();
    } catch (submitError) {
      setError(
        submitError instanceof ApiError || submitError instanceof Error
          ? submitError.message
          : "Falha ao criar agendamento.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (session.loading || !session.data) {
    return (
      <div className="loading-screen">
        <div className="loading-card">
          <h2>Carregando sessao</h2>
          <p className="lead">Aguardando contexto autenticado do backend.</p>
        </div>
      </div>
    );
  }

  if (!session.data.authenticated) {
    return null;
  }

  const nextAppointment =
    [...appointments]
      .filter((appointment) => !Number.isNaN(new Date(appointment.appointment_date).getTime()))
      .sort(
        (left, right) =>
          new Date(left.appointment_date).getTime() - new Date(right.appointment_date).getTime(),
      )[0] ?? null;

  return (
    <AppShell
      session={session.data}
      subtitle="Operacao inicial da agenda no frontend novo, ainda apoiada pela sessao e regras do backend Flask."
      title="Agendamentos"
    >
      <section className="overview-grid">
        <article className="overview-band">
          <span className="meta-label">Total</span>
          <h2>{appointments.length}</h2>
          <p className="lead">Consultas visiveis para a clinica atualmente selecionada.</p>
        </article>
        <article className="overview-band">
          <span className="meta-label">Proximo slot</span>
          <h2>{nextAppointment ? formatDateTime(nextAppointment.appointment_date) : "--"}</h2>
          <p className="lead">
            {nextAppointment
              ? `Paciente ${nextAppointment.patient_name}`
              : "Ainda nao ha eventos para projetar a operacao da agenda."}
          </p>
        </article>
      </section>

      <section className="analytics-grid">
        <form
          className="record-form"
          onSubmit={(event) => {
            startTransition(() => {
              void handleSubmit(event);
            });
          }}
        >
          <p className="eyebrow">Novo agendamento</p>
          <h2>Criar consulta</h2>
          <p className="lead">
            O backend continua validando o contexto da clinica e ja registra o evento na
            timeline do paciente.
          </p>

          <div className="form-stack field-stack">
            <label>
              Nome do paciente
              <input
                className="login-field"
                onChange={(event) =>
                  setForm((current) => ({ ...current, patient_name: event.target.value }))
                }
                placeholder="Joao Silva"
                value={form.patient_name}
              />
            </label>

            <label>
              Data e hora
              <input
                className="login-field"
                onChange={(event) =>
                  setForm((current) => ({ ...current, appointment_date: event.target.value }))
                }
                type="datetime-local"
                value={form.appointment_date}
              />
              <span className="input-hint">
                O frontend converte para ISO 8601 antes de enviar a API.
              </span>
            </label>
          </div>

          {error ? <div className="inline-error">{error}</div> : null}
          {saveMessage ? <div className="inline-empty">{saveMessage}</div> : null}

          <div className="action-cluster">
            <button className="button-primary" disabled={busy} type="submit">
              {busy ? "Salvando..." : "Criar agendamento"}
            </button>
            <button
              className="button-secondary"
              onClick={() => {
                setForm({ patient_name: "", appointment_date: "" });
                setSaveMessage(null);
                setError(null);
              }}
              type="button"
            >
              Limpar
            </button>
          </div>
        </form>

        <article className="grid-panel">
          <p className="eyebrow">Fila de agenda</p>
          <h2>Consultas registradas</h2>
          {loading ? (
            <div className="inline-empty">Carregando agenda...</div>
          ) : appointments.length ? (
            <div className="appointment-list">
              {appointments.map((appointment) => (
                <article className="appointment-item" key={appointment.id}>
                  <header>
                    <div>
                      <p className="eyebrow">Agendamento #{appointment.id}</p>
                      <h2>{appointment.patient_name}</h2>
                    </div>
                    <StatusPill
                      label={humanize(appointment.status)}
                      tone={statusTone(appointment.status)}
                    />
                  </header>
                  <div className="kpi-line">
                    <span>{formatDateTime(appointment.appointment_date)}</span>
                    <span>
                      {appointment.patient_id ? `Paciente #${appointment.patient_id}` : "Sem paciente"}
                    </span>
                  </div>
                  <p className="lead">Criado em {formatDateTime(appointment.created_at)}.</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="inline-empty">Nenhum agendamento encontrado para esta clinica.</div>
          )}
        </article>
      </section>
    </AppShell>
  );
}
