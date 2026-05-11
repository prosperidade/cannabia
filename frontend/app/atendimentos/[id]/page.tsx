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

// ── Prescription result rendering helpers (Sprint 1 C.1.4) ────────────────
// prescription_result vem como Record<string, unknown> do backend (sem
// tipagem estrita no AttendanceReport). Helpers fazem narrowing seguro
// para extrair campos esperados sem quebrar quando ausentes (reports
// pre-C.1 nao tem o bloco).

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function PrescriptionResultBlock({ data }: { data: Record<string, unknown> }) {
  const finalDosage = asRecord(data.final_dosage) ?? {};
  const summary = asRecord(data.rules_engine_summary) ?? {};
  const titration = Array.isArray(finalDosage.titration_protocol)
    ? (finalDosage.titration_protocol as unknown[])
    : [];
  const cyp450 = asStringList(data.cyp450_interactions);
  const alerts = asStringList(data.monitoring_alerts);
  const checkpoints = asStringList(finalDosage.monitoring_checkpoints);
  const clampApplied = data.safety_clamp_applied === true;
  const defaultsUsed = data.dosage_defaults_used === true;
  const ratio = asString(finalDosage.cannabinoid_ratio) ?? "—";
  const route = asString(finalDosage.administration_route) ?? "—";
  const spectrum = asString(finalDosage.spectrum);
  const maxDaily = asNumber(finalDosage.max_daily_mg);
  const concentration = asNumber(finalDosage.concentration_mg_ml);
  const confidence = asNumber(data.confidence_score);
  const rationale = asString(finalDosage.clinical_rationale);

  return (
    <article className="content-card">
      <header className="attendance-card">
        <div>
          <p className="eyebrow">Recomendacao do Prescritor</p>
          <h2>{ratio} · {humanize(route)}</h2>
          {spectrum ? <p className="lead">Espectro: {humanize(spectrum)}</p> : null}
        </div>
        {maxDaily !== null ? (
          <div style={{ textAlign: "right" }}>
            <p className="eyebrow">Dose maxima diaria</p>
            <strong style={{ fontSize: "1.4rem" }}>{maxDaily} mg</strong>
            {concentration !== null ? (
              <p className="lead">{concentration} mg/mL</p>
            ) : null}
          </div>
        ) : null}
      </header>

      <div className="pill-row" style={{ marginTop: 12 }}>
        {clampApplied ? (
          <span
            className="mini-pill"
            title={
              asString(data.safety_clamp_reason)
              ?? "Rules Engine ajustou a dose por seguranca."
            }
          >
            ⚠ Dosagem ajustada por seguranca
          </span>
        ) : null}
        {defaultsUsed ? (
          <span
            className="mini-pill"
            title="Anamnese sem peso e/ou uso prévio de cannabis cadastrados — defaults conservadores aplicados (peso=70kg, naive)."
          >
            ⓘ Dosagem com defaults conservadores
          </span>
        ) : null}
        {confidence !== null ? (
          <span className="mini-pill">
            Confianca: {(confidence * 100).toFixed(0)}%
          </span>
        ) : null}
      </div>

      {cyp450.length ? (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow">Interacoes CYP450 detectadas</p>
          <ul className="lead" style={{ paddingLeft: 18, margin: 0 }}>
            {cyp450.map((item, idx) => (
              <li key={`cyp-${idx}`}>⚠ {item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {alerts.length ? (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow">Alertas de monitoramento</p>
          <ul className="lead" style={{ paddingLeft: 18, margin: 0 }}>
            {alerts.map((item, idx) => (
              <li key={`alert-${idx}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {titration.length ? (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow">Protocolo de titulacao</p>
          <div className="timeline-stack">
            {titration.map((stepRaw, idx) => {
              const step = asRecord(stepRaw);
              if (!step) return null;
              const phase = asString(step.phase) ?? `fase ${idx + 1}`;
              const range = asString(step.day_range) ?? "—";
              const drops = asNumber(step.drops_per_dose);
              const doses = asNumber(step.doses_per_day);
              const stepMg = asNumber(step.total_daily_mg);
              const obs = asString(step.observations);
              return (
                <div className="timeline-card" key={`tit-${idx}`}>
                  <header>
                    <div>
                      <strong>{humanize(phase)} · {range}</strong>
                      {drops !== null && doses !== null ? (
                        <p className="lead">{drops} gota(s) · {doses}x ao dia</p>
                      ) : null}
                    </div>
                    {stepMg !== null ? (
                      <span className="mini-pill">{stepMg} mg/dia</span>
                    ) : null}
                  </header>
                  {obs ? <p className="lead">{obs}</p> : null}
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      {checkpoints.length ? (
        <div style={{ marginTop: 16 }}>
          <p className="eyebrow">Marcos de monitoramento clinico</p>
          <ul className="lead" style={{ paddingLeft: 18, margin: 0 }}>
            {checkpoints.map((item, idx) => (
              <li key={`chk-${idx}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {summary.age_adjustment || summary.recommended_ratio ? (
        <p
          className="lead"
          style={{ marginTop: 12, fontSize: "0.85rem", opacity: 0.75 }}
        >
          Rules Engine: {asString(summary.age_adjustment) ?? "—"}
          {asString(summary.recommended_ratio)
            ? ` · ratio recomendado: ${summary.recommended_ratio as string}`
            : ""}
        </p>
      ) : null}

      {rationale ? (
        <details style={{ marginTop: 16 }}>
          <summary className="eyebrow" style={{ cursor: "pointer" }}>
            Racional clinico (LLM)
          </summary>
          <p className="lead" style={{ marginTop: 8 }}>{rationale}</p>
        </details>
      ) : null}
    </article>
  );
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

          {report.prescription_result
            ? <PrescriptionResultBlock data={report.prescription_result} />
            : null}
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
