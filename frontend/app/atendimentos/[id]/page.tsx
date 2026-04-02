"use client";

import { useParams, useRouter } from "next/navigation";
import { startTransition, type FormEvent, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { StatusPill } from "@/components/status-pill";
import {
  ApiError,
  getAttendance,
  reviewAttendance,
  saveMedicalRecord,
} from "@/lib/api";
import { formatDateTime, humanize, toStringArray } from "@/lib/format";
import { useApiSession } from "@/lib/use-api-session";
import type { AttendanceDetail, MedicalRecordPayload } from "@/lib/types";

function prettyJson(input: unknown) {
  return JSON.stringify(input, null, 2);
}

function splitText(raw: string) {
  return raw
    .replaceAll("\r", "")
    .split(/[\n,]/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

export default function AttendanceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const session = useApiSession();
  const [detail, setDetail] = useState<AttendanceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [form, setForm] = useState({
    consultation_status: "em_revisao",
    medical_observations: "",
    clinical_assessment: "",
    conduct: "",
    requested_exams: "",
    follow_up_plan: "",
  });

  useEffect(() => {
    if (session.loading) {
      return;
    }
    if (!session.data?.authenticated) {
      router.replace("/login");
      return;
    }

    async function loadDetail() {
      setLoading(true);
      setError(null);
      setSaveMessage(null);
      try {
        const data = await getAttendance(params.id);
        setDetail(data);
        setForm({
          consultation_status: data.consultation_entry?.status ?? "em_revisao",
          medical_observations: data.consultation_entry?.medical_observations ?? "",
          clinical_assessment: data.consultation_entry?.clinical_assessment ?? "",
          conduct: data.consultation_entry?.conduct ?? "",
          requested_exams: data.consultation_entry?.requested_exams?.join(", ") ?? "",
          follow_up_plan: data.consultation_entry?.follow_up_plan ?? "",
        });
      } catch (loadError) {
        setError(loadError instanceof ApiError ? loadError.message : "Falha ao carregar atendimento.");
      } finally {
        setLoading(false);
      }
    }

    void loadDetail();
  }, [params.id, router, session.data, session.loading]);

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

  async function refreshDetail() {
    const data = await getAttendance(params.id);
    setDetail(data);
    setForm({
      consultation_status: data.consultation_entry?.status ?? "em_revisao",
      medical_observations: data.consultation_entry?.medical_observations ?? "",
      clinical_assessment: data.consultation_entry?.clinical_assessment ?? "",
      conduct: data.consultation_entry?.conduct ?? "",
      requested_exams: data.consultation_entry?.requested_exams?.join(", ") ?? "",
      follow_up_plan: data.consultation_entry?.follow_up_plan ?? "",
    });
  }

  async function handleReview() {
    if (!session.data) return;
    setReviewBusy(true);
    setError(null);
    try {
      await reviewAttendance(params.id, session.data.csrf_token);
      await refreshDetail();
      setSaveMessage("Atendimento revisado com sucesso.");
    } catch (reviewError) {
      setError(reviewError instanceof ApiError ? reviewError.message : "Falha ao revisar atendimento.");
    } finally {
      setReviewBusy(false);
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session.data) return;

    setSaveBusy(true);
    setError(null);
    setSaveMessage(null);

    const payload: MedicalRecordPayload = {
      consultation_status: form.consultation_status,
      medical_observations: form.medical_observations,
      clinical_assessment: form.clinical_assessment,
      conduct: form.conduct,
      requested_exams: splitText(form.requested_exams),
      follow_up_plan: form.follow_up_plan,
    };

    try {
      await saveMedicalRecord(params.id, session.data.csrf_token, payload);
      await refreshDetail();
      setSaveMessage("Prontuario salvo com sucesso.");
    } catch (saveError) {
      setError(saveError instanceof ApiError ? saveError.message : "Falha ao salvar prontuario.");
    } finally {
      setSaveBusy(false);
    }
  }

  if (loading || !detail) {
    return (
      <AppShell
        session={session.data}
        subtitle="Carregando o caso clinico completo pela API v1."
        title="Detalhe do atendimento"
      >
        <div className="inline-empty">Carregando atendimento...</div>
      </AppShell>
    );
  }

  const report = detail.report;

  return (
    <AppShell
      session={session.data}
      subtitle="Timeline, IA e prontuario agora compartilhando a mesma superficie no frontend novo."
      title={`Atendimento #${report.id}`}
    >
      {error ? <div className="inline-error">{error}</div> : null}
      {saveMessage ? <div className="inline-empty">{saveMessage}</div> : null}

      <section className="detail-grid">
        <div className="detail-stack">
          <article className="content-card">
            <header className="attendance-card">
              <div>
                <p className="eyebrow">Paciente</p>
                <h2>{report.patient_name}</h2>
                <p className="lead">{report.phone}</p>
              </div>
              <StatusPill
                label={humanize(report.status)}
                tone={report.status === "revisado" ? "ok" : "warn"}
              />
            </header>
            <div className="pill-row">
              <span className="mini-pill">{report.report_model}</span>
              <span className="mini-pill">{report.rag_chunks_used} chunks RAG</span>
              <span className="mini-pill">{formatDateTime(report.created_at)}</span>
            </div>
            <div className="button-row" style={{ marginTop: 18 }}>
              <button
                className="button-primary"
                disabled={reviewBusy || report.status === "revisado"}
                onClick={() => {
                  startTransition(() => {
                    void handleReview();
                  });
                }}
                type="button"
              >
                {report.status === "revisado"
                  ? "Caso revisado"
                  : reviewBusy
                    ? "Revisando..."
                    : "Marcar como revisado"}
              </button>
            </div>
          </article>

          <article className="content-card">
            <p className="eyebrow">Anamnese estruturada</p>
            <pre>{prettyJson(report.anamnesis_data)}</pre>
          </article>

          <article className="content-card">
            <p className="eyebrow">Analise clinica e plano terapeutico</p>
            <pre>
              {prettyJson({
                clinical_analysis: report.clinical_analysis,
                treatment_plan: report.treatment_plan,
                scientific_report: report.scientific_report,
              })}
            </pre>
          </article>
        </div>

        <div className="record-stack">
          <form
            className="record-form"
            onSubmit={(event) => {
              startTransition(() => {
                void handleSave(event);
              });
            }}
          >
            <p className="eyebrow">Prontuario longitudinal</p>
            <h2>Registro clinico do medico</h2>
            <p className="record-copy">
              Esta e a primeira superficie do prontuario no frontend novo, consumindo a API
              Flask em tempo real.
            </p>

            <div className="record-grid">
              <label>
                Status clinico
                <select
                  className="record-select"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      consultation_status: event.target.value,
                    }))
                  }
                  value={form.consultation_status}
                >
                  <option value="em_revisao">Em revisao</option>
                  <option value="consulta_realizada">Consulta realizada</option>
                  <option value="consulta_nao_realizada">Consulta nao realizada</option>
                  <option value="acompanhamento_definido">Acompanhamento definido</option>
                </select>
              </label>

              <label>
                Exames solicitados
                <textarea
                  className="record-textarea"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      requested_exams: event.target.value,
                    }))
                  }
                  rows={4}
                  value={form.requested_exams}
                />
              </label>

              <label className="span-2">
                Observacoes medicas
                <textarea
                  className="record-textarea"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      medical_observations: event.target.value,
                    }))
                  }
                  value={form.medical_observations}
                />
              </label>

              <label>
                Avaliacao clinica
                <textarea
                  className="record-textarea"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      clinical_assessment: event.target.value,
                    }))
                  }
                  value={form.clinical_assessment}
                />
              </label>

              <label>
                Conduta
                <textarea
                  className="record-textarea"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      conduct: event.target.value,
                    }))
                  }
                  value={form.conduct}
                />
              </label>

              <label className="span-2">
                Plano de acompanhamento
                <textarea
                  className="record-textarea"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      follow_up_plan: event.target.value,
                    }))
                  }
                  value={form.follow_up_plan}
                />
              </label>
            </div>

            <div className="button-row" style={{ marginTop: 18 }}>
              <button className="action-button" disabled={saveBusy} type="submit">
                {saveBusy ? "Salvando..." : "Salvar prontuario"}
              </button>
            </div>
          </form>

          <article className="grid-panel">
            <p className="eyebrow">Timeline do paciente</p>
            {detail.timeline.length ? (
              <div className="timeline-stack">
                {detail.timeline.map((event) => (
                  <div className="timeline-card" key={event.id}>
                    <header>
                      <div>
                        <strong>{event.title}</strong>
                        <p className="lead">{event.description ?? "Sem descricao operacional."}</p>
                      </div>
                      <span>{formatDateTime(event.event_time)}</span>
                    </header>
                    <div className="timeline-tags">
                      <span className="mini-pill">{humanize(event.event_type)}</span>
                      {event.journey_stage ? (
                        <span className="mini-pill">{humanize(event.journey_stage)}</span>
                      ) : null}
                      {event.source_type ? (
                        <span className="mini-pill">{event.source_type}</span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="inline-empty">Nenhum evento longitudinal registrado ainda.</div>
            )}
          </article>

          <article className="grid-panel">
            <p className="eyebrow">Entradas do prontuario</p>
            {detail.medical_record_entries.length ? (
              <div className="record-list">
                {detail.medical_record_entries.map((entry) => (
                  <div className="record-card" key={entry.id}>
                    <header>
                      <div>
                        <strong>{entry.title}</strong>
                        <p className="lead">
                          {entry.author_name ?? "sistema"} · {formatDateTime(entry.created_at)}
                        </p>
                      </div>
                      <StatusPill label={humanize(entry.status)} tone="info" />
                    </header>
                    <div className="timeline-tags">
                      <span className="mini-pill">{humanize(entry.entry_type)}</span>
                      {toStringArray(entry.requested_exams).map((exam) => (
                        <span className="mini-pill" key={`${entry.id}-${exam}`}>
                          {exam}
                        </span>
                      ))}
                    </div>
                    {entry.clinical_assessment ? <p className="lead">{entry.clinical_assessment}</p> : null}
                    {entry.conduct ? <p className="lead">{entry.conduct}</p> : null}
                    {entry.follow_up_plan ? <p className="lead">{entry.follow_up_plan}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="inline-empty">Ainda nao existem entradas clinicas neste prontuario.</div>
            )}
          </article>
        </div>
      </section>
    </AppShell>
  );
}
