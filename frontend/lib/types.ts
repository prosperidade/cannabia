export type ApiSessionResponse = {
  authenticated: boolean;
  user: {
    id: number;
    username: string;
    role: string;
    global_role?: string;
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

export type ApiListMeta = {
  page: number;
  page_size: number;
  total: number;
};

export type PaginatedResult<T> = {
  items: T[];
  meta: ApiListMeta;
};

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
