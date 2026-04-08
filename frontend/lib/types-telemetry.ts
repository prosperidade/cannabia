/* ─── Telemetry / IoT types ──────────────────────────────────────────
   Espelham as rotas em src/web/routes/telemetry.py.
   Consumidos pelo dashboard de telemetria pós-consulta e diário de
   sintomas do paciente.
   ──────────────────────────────────────────────────────────────────── */

// ── IoT Sources ────────────────────────────────────────────────────

/** Fontes de dados permitidas pelo backend. */
export type IoTSource =
  | "apple_health"
  | "google_fit"
  | "manual"
  | "withings"
  | "fitbit";

/** Tipos de métrica aceitos pelo backend. */
export type IoTMetricType =
  | "sleep_hours"
  | "sleep_score"
  | "heart_rate"
  | "heart_rate_variability"
  | "spo2"
  | "steps"
  | "pain_score"
  | "anxiety_score"
  | "mood_score"
  | "blood_pressure_systolic"
  | "blood_pressure_diastolic"
  | "body_temperature"
  | "respiratory_rate"
  | "weight";

// ── IoT Reading ────────────────────────────────────────────────────

export type IoTReading = {
  id: number;
  clinic_id: number;
  patient_id: number;
  source: IoTSource;
  metric_type: IoTMetricType;
  value: number;
  unit: string;
  recorded_at: string;
  /** Dados extras do dispositivo (ex: { sleep_stage, device }). */
  metadata?: Record<string, unknown>;
};

/** Payload para ingestão de uma única leitura (POST /api/telemetry/iot). */
export type IoTReadingPayload = {
  patient_id: number;
  source: IoTSource;
  metric_type: IoTMetricType;
  value: number;
  unit: string;
  /** ISO 8601 timestamp. */
  recorded_at: string;
  metadata?: Record<string, unknown>;
};

/** Payload para ingestão em batch. */
export type IoTBatchPayload = {
  readings: IoTReadingPayload[];
};

/** Resposta de ingestão em batch (202). */
export type IoTBatchResponse = {
  status: "accepted";
  stored: number;
  ids: number[];
  warnings?: Array<{ index: number; error: string }>;
};

/** Resposta de query de série temporal (GET /api/telemetry/iot/<patient_id>). */
export type IoTTimeseriesResponse = {
  patient_id: number;
  metric_type: IoTMetricType;
  count: number;
  readings: IoTReading[];
};

// ── Follow-Up CRM ──────────────────────────────────────────────────

/** Status do follow-up no ciclo de vida CRM. */
export type FollowUpStatus =
  | "scheduled"
  | "sent"
  | "responded"
  | "missed"
  | "cancelled";

/** Tipo de follow-up (canal ou categoria). */
export type FollowUpType = "whatsapp" | "email" | "sms" | "phone_call";

export type FollowUp = {
  patient_id: number;
  type: FollowUpType;
  status: FollowUpStatus;
  scheduled_at: string;
  sent_at?: string | null;
  channel?: string | null;
  message?: string | null;
};

/** Resposta de GET /api/telemetry/followups/<patient_id>. */
export type FollowUpListResponse = {
  patient_id: number;
  count: number;
  followups: FollowUp[];
};

// ── Symptom Diary (frontend-side) ──────────────────────────────────

/** Entrada do diário de sintomas preenchido pelo paciente. */
export type SymptomDiaryEntry = {
  date: string;
  /** Escala 0-10. */
  pain_level: number;
  /** Escala 0-10. */
  sleep_quality: number;
  /** Escala 0-10. */
  mood: number;
  notes?: string;
};
