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

export type AttendanceDetail = {
  report: AttendanceReport;
  timeline: TimelineEvent[];
  medical_record_entries: MedicalRecordEntry[];
  consultation_entry: MedicalRecordEntry | null;
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
