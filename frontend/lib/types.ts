export type ApiSessionResponse = {
  authenticated: boolean;
  user: {
    id: number;
    username: string;
    role: string;
    global_role?: string;
    /** True quando o user e admin do tenant (independente do role
     *  principal). Combina com Medico para gerar "medico-dono". */
    is_clinic_admin?: boolean;
  } | null;
  context: {
    clinic_id: number | null;
    clinic_role: string | null;
    tenant_id: number | null;
    tenant_role: string | null;
    tenant_type: string | null;
  } | null;
  csrf_token: string;
};

export type DashboardMetrics = {
  total_messages: number;
  total_patients: number;
  total_appointments: number;
  total_ai: number;
};

export type DashboardContactStat = {
  label: string;
  count: number;
};

export type DashboardDayStat = {
  date: string;
  count: number;
};

export type DashboardMessage = {
  id: number;
  sender: string;
  contact_name: string | null;
  message_text: string | null;
  timestamp: string;
};

export type MessageItem = DashboardMessage;

export type MessageContactOption = {
  sender: string;
  label: string;
  count: number;
};

export type DashboardData = {
  metrics: DashboardMetrics;
  charts: {
    messages_by_contact: DashboardContactStat[];
    messages_by_day: DashboardDayStat[];
  };
};

export type AttendanceListItem = {
  id: number;
  patient_id: number | null;
  patient_name: string;
  phone: string;
  status: string;
  rag_chunks_used: number;
  report_model: string;
  created_at: string;
  risk_level: string | null;
  weight_kg: string | null;
  height_cm: string | null;
  main_complaint: string | null;
  appointment_id: number | null;
};

export type TimelineEvent = {
  id: number;
  event_type: string;
  journey_stage: string | null;
  title: string;
  description: string | null;
  source_type: string | null;
  source_id: number | null;
  event_time: string;
  metadata: Record<string, unknown>;
};

export type MedicalRecordEntry = {
  id: number;
  medical_record_id: number;
  author_user_id: number | null;
  author_name: string | null;
  entry_type: string;
  source_report_id: number | null;
  title: string;
  status: string;
  medical_observations: string | null;
  clinical_assessment: string | null;
  conduct: string | null;
  requested_exams: string[];
  follow_up_plan: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AttendanceReport = {
  id: number;
  patient_id: number | null;
  patient_name: string;
  phone: string;
  status: string;
  rag_chunks_used: number;
  report_model: string;
  created_at: string;
  anamnesis_data: Record<string, unknown>;
  clinical_analysis: Record<string, unknown>;
  treatment_plan: Record<string, unknown>;
  prescription_result?: Record<string, unknown>;
  scientific_report: Record<string, unknown>;
};

export type PrescriptionContractField = {
  field: string;
  label: string;
};

export type PrescriptionContract = {
  ready: boolean;
  readiness: "ready" | "missing_required";
  message: string;
  required_fields: PrescriptionContractField[];
  missing_required_fields: PrescriptionContractField[];
  missing_optional_fields: PrescriptionContractField[];
  resolved_values: Record<string, unknown>;
  source_map: Record<string, string>;
  report_id: number | null;
  patient_id: number | null;
};

export type TriageSubmissionResult = {
  report_id: number;
  patient_id: number;
  clinic_id: number;
  patient_name: string;
  status: string;
  prescription_contract: PrescriptionContract;
};

export type PaymentRequest = {
  id: number;
  tenant_id: number;
  clinic_id: number;
  patient_id: number | null;
  prescription_id: number | null;
  external_id: string;
  description: string | null;
  amount_cents: number;
  currency: string;
  method: string;
  status: "pending" | "paid" | "expired" | "cancelled" | "refunded";
  provider: string;
  pix_payload: string | null;
  pix_qr_image_url: string | null;
  pix_key: string | null;
  expires_at: string | null;
  paid_at: string | null;
  paid_amount_cents: number | null;
  provider_ref: string | null;
  provider_metadata: Record<string, unknown>;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type PaymentTransaction = {
  id: number;
  payment_request_id: number;
  tenant_id: number;
  provider: string;
  provider_event_id: string | null;
  event_type: string;
  status: string;
  amount_cents: number;
  currency: string;
  payer_name: string | null;
  payer_document: string | null;
  payer_account: string | null;
  received_at: string;
};

export type PaymentDetail = PaymentRequest & {
  transactions: PaymentTransaction[];
};

export type PaymentSummary = {
  pending?: { count: number; total_cents: number };
  paid?: { count: number; total_cents: number; paid_cents: number };
  expired?: { count: number; total_cents: number };
  cancelled?: { count: number; total_cents: number };
  refunded?: { count: number; total_cents: number };
};

export type TriageLinkContext = {
  clinic_id: number;
  clinic_label: string;
  appointment_id?: number;
  patient_id?: number;
  patient_name?: string;
  patient_phone?: string;
  link_id?: number;
};

export type TriageLinkIssueResult = TriageLinkContext & {
  token: string;
  url: string;
  issued_at: string;
  expires_at: string;
  link_id?: number;
};

export type AttendanceDetail = {
  report: AttendanceReport;
  timeline: TimelineEvent[];
  medical_record_entries: MedicalRecordEntry[];
  consultation_entry: MedicalRecordEntry | null;
  prescription_contract: PrescriptionContract;
};

export type MedicalRecordPayload = {
  consultation_status: string;
  medical_observations: string;
  clinical_assessment: string;
  conduct: string;
  requested_exams: string[];
  follow_up_plan: string;
};

export type AppointmentItem = {
  id: number;
  patient_id: number | null;
  patient_name: string;
  appointment_date: string;
  status: string;
  created_at: string;
};

export type AppointmentPayload = {
  patient_name: string;
  appointment_date: string;
};

export type AiAuditSummary = {
  total_execucoes: number;
  total_tokens: number;
  total_cost_usd: number;
  sucessos: number;
  erros: number;
  bloqueios: number;
  tempo_medio_ms: number;
};

export type AiAuditLog = {
  id: number;
  patient_id: number | null;
  status: string;
  endpoint: string;
  model: string;
  total_tokens: number;
  estimated_cost_usd: number;
  error_message: string | null;
  created_at: string;
};

export type AiAuditData = {
  summary: AiAuditSummary;
  recent_logs: AiAuditLog[];
  filters?: {
    status: string | null;
    days: number | null;
    limit: number;
  };
};

// ── Conversations (Inbox Clinica) ──

export type Conversation = {
  id: number;
  clinic_id: number;
  patient_id: number | null;
  contact_phone: string;
  contact_name: string | null;
  patient_name_resolved: string | null;
  channel: string;
  status: string;
  assigned_to: number | null;
  last_message_at: string | null;
  last_message_preview: string | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: number;
  conversation_id: number;
  direction: "inbound" | "outbound";
  sender_type: string;
  sender_name: string | null;
  message_text: string | null;
  message_type: string;
  status: string;
  created_at: string;
};

export type ConversationDetail = {
  conversation: Conversation;
  messages: ConversationMessage[];
};

/**
 * Envelope canonico de paginacao (Sprint 2 Track Page + Sprint 3 Tier-2).
 *
 * Tipo CANONICO unico (Sprint 3 Page-Migration: removeu o concorrente
 * `PaginatedResult<T>` + `ApiListMeta`, que nao tinha consumers reais).
 *
 * Contrato backend: src/web/pagination.py::paginated_response
 *
 * Endpoints Tier-1 (Sprint 2):
 *   - GET /api/v1/appointments
 *   - GET /api/v1/attendances    (relatorios de anamnese)
 *   - GET /api/v1/conversations
 *   - GET /api/v1/admin/ai-metrics?paginated=1   (recent_logs vira envelope)
 *
 * Endpoints Tier-2 (Sprint 3):
 *   - GET /api/v1/governance/documents?paginated=1
 *   - GET /api/v1/governance/rts?paginated=1
 *   - GET /api/v1/governance/capacity?paginated=1
 *   - GET /api/v1/patients/<id>/medical-record    (entries envelope opt-in)
 *   - GET /api/v1/patients/<id>/timeline          (cursor-based: ?before_id)
 *
 * Query params suportados:
 *   - ?limit=50         (default; max=200; >200 -> HTTP 400 invalid_limit)
 *   - ?offset=0         (default; offset-based)
 *   - ?include_total=1  (opt-in pra COUNT(*); custa)
 *   - ?legacy=1         (DEPRECATED, removal 2026-08-01 — Sprint 4)
 *   - ?before_id=N      (cursor-based; so em timeline e messages)
 *
 * has_more:
 *   - Quando total e conhecido: (offset + items.length) < total
 *   - Senao: heuristica LIMIT_PLUS_ONE_TRICK (true se backend trouxe limit+1)
 */
export type Paginated<T> = {
  items: T[];
  total: number | null;
  limit: number;
  offset: number;
  has_more: boolean;
  /** Cursor-based feeds (ex.: patient_timeline). Sprint 3. */
  next_cursor?: number | null;
};
