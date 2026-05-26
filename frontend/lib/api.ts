import type {
  AiAuditData,
  AiAuditLog,
  ApiSessionResponse,
  AppointmentItem,
  AppointmentPayload,
  AttendanceDetail,
  AttendanceListItem,
  Conversation,
  DashboardData,
  DashboardMessage,
  MessageContactOption,
  MessageItem,
  MedicalRecordPayload,
  Paginated,
  TriageSubmissionResult,
  TriageLinkContext,
  TriageLinkIssueResult,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";

type ApiEnvelope<T> = {
  data: T;
  meta?: Record<string, unknown>;
};

type ApiFailure = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/**
 * Sprint 3 Page-Migration: detecta header `Deprecation: true` da response
 * e avisa via console.warn pra incentivar migracao antes do Sunset
 * (2026-08-01, Sprint 4).
 */
function warnIfDeprecated(path: string, response: Response): void {
  const dep = response.headers.get("Deprecation");
  if (!dep) return;
  const sunset = response.headers.get("Sunset") ?? "Sprint 4";
  // Reduz ruido em runtime de testes (jsdom).
  if (typeof console !== "undefined" && typeof console.warn === "function") {
    console.warn(
      `[API] endpoint ${path} marcado como deprecated ` +
        `(?legacy=1) — migrar antes de ${sunset}.`,
    );
  }
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<ApiEnvelope<T>> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  warnIfDeprecated(path, response);

  const raw = response.headers.get("content-type")?.includes("application/json")
    ? ((await response.json()) as ApiEnvelope<T> | ApiFailure)
    : null;

  if (!response.ok) {
    const failure = raw as ApiFailure | null;
    throw new ApiError(
      response.status,
      failure?.error?.code ?? "request_failed",
      failure?.error?.message ?? "Falha ao processar a requisicao.",
      failure?.error?.details,
    );
  }

  return raw as ApiEnvelope<T>;
}

export async function getSession() {
  const response = await request<ApiSessionResponse>("/session/me");
  return response.data;
}

export async function login(username: string, password: string) {
  const response = await request<ApiSessionResponse>("/session/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  return response.data;
}

export async function logout(csrfToken: string) {
  const response = await request<{ success: boolean }>("/session/logout", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({}),
  });
  return response.data;
}

export async function getDashboard() {
  const response = await request<DashboardData>("/dashboard");
  return response.data;
}

export async function getDashboardMessages(page = 1, pageSize = 8) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  const response = await request<DashboardMessage[]>(`/dashboard/messages?${params.toString()}`);
  return response.data;
}

type MessageFilters = {
  sender?: string;
  search?: string;
};

type AiMetricsFilters = {
  status?: string;
  days?: number;
  limit?: number;
};

export async function listMessages(
  page = 1,
  pageSize = 50,
  filters: MessageFilters = {},
): Promise<{ items: MessageItem[]; total: number }> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (filters.sender?.trim()) {
    params.set("sender", filters.sender.trim());
  }
  if (filters.search?.trim()) {
    params.set("search", filters.search.trim());
  }
  const response = await request<MessageItem[]>(`/messages?${params.toString()}`);
  const metaTotal =
    (response.meta as { total?: number } | undefined)?.total ??
    response.data.length;
  return {
    items: response.data,
    total: metaTotal,
  };
}

export async function listMessageContacts(search?: string) {
  const params = new URLSearchParams({ limit: "50" });
  if (search?.trim()) {
    params.set("search", search.trim());
  }
  const response = await request<MessageContactOption[]>(`/messages/contacts?${params.toString()}`);
  return response.data;
}

/**
 * Sprint 3 Page-Migration: envelope `Paginated<AttendanceListItem>` (default
 * a partir do contrato canonico). Sem args = primeira pagina (limit=50).
 *
 * Use `listAttendancesAll()` se quiser o array nu (compat path Sprint 1).
 */
export async function listAttendances(opts?: {
  status?: string;
  limit?: number;
  offset?: number;
  include_total?: boolean;
}): Promise<Paginated<AttendanceListItem>> {
  const params = new URLSearchParams();
  if (opts?.status && opts.status !== "all") params.set("status", opts.status);
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.include_total) params.set("include_total", "1");
  const query = params.toString() ? `?${params}` : "";
  const response = await request<Paginated<AttendanceListItem>>(
    `/attendances${query}`,
  );
  return response.data;
}

/** Convenience: extrai items diretos do envelope (substituicao drop-in). */
export async function listAttendancesItems(
  status?: string,
): Promise<AttendanceListItem[]> {
  const env = await listAttendances({ status, limit: 200 });
  return env.items;
}

export async function getAttendance(id: string) {
  const response = await request<AttendanceDetail>(`/attendances/${id}`);
  return response.data;
}

export async function reviewAttendance(id: string, csrfToken: string) {
  const response = await request<{ reviewed: boolean; report_id: number; status: string }>(
    `/attendances/${id}/review`,
    {
      method: "POST",
      headers: {
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({}),
    },
  );
  return response.data;
}

export async function saveMedicalRecord(
  id: string,
  csrfToken: string,
  payload: MedicalRecordPayload,
) {
  const response = await request<{
    saved: boolean;
    medical_record_id: number;
    entry_id: number;
    created: boolean;
  }>(`/attendances/${id}/medical-record`, {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.data;
}

/**
 * Sprint 3 Page-Migration: envelope `Paginated<AppointmentItem>`.
 */
export async function listAppointments(opts?: {
  limit?: number;
  offset?: number;
  include_total?: boolean;
}): Promise<Paginated<AppointmentItem>> {
  const params = new URLSearchParams();
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  if (opts?.include_total) params.set("include_total", "1");
  const query = params.toString() ? `?${params}` : "";
  const response = await request<Paginated<AppointmentItem>>(
    `/appointments${query}`,
  );
  return response.data;
}

export async function createAppointment(csrfToken: string, payload: AppointmentPayload) {
  const response = await request<{ created: boolean; appointment_id: number }>("/appointments", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function submitTriageIntake(csrfToken: string, payload: Record<string, unknown>) {
  const response = await request<TriageSubmissionResult>("/intake/triage", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function createAppointmentTriageLink(
  appointmentId: number,
  csrfToken: string,
  payload?: { patient_phone?: string },
) {
  const response = await request<TriageLinkIssueResult>(
    `/appointments/${appointmentId}/triage-link`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload ?? {}),
    },
  );
  return response.data;
}

export async function createTriageLink(csrfToken: string) {
  const response = await request<TriageLinkIssueResult>("/intake/triage-link", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({}),
  });
  return response.data;
}

export async function resolveTriageLink(token: string) {
  const params = new URLSearchParams({ token });
  const response = await request<TriageLinkContext>(`/intake/triage-link?${params.toString()}`);
  return response.data;
}

export async function calculateDosage(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/prescriptions/calculate", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}

export async function emitPrescription(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/prescriptions/emit", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}

export async function listPrescriptions() {
  return request<Record<string, unknown>[]>("/prescriptions");
}

export async function getPrescription(id: string) {
  return request<Record<string, unknown>>(`/prescriptions/${id}`);
}

export async function listTenants() {
  const response = await request<import("@/lib/types-admin").Tenant[]>("/admin/tenants");
  return response.data;
}

export async function createTenant(
  csrfToken: string,
  payload: { legal_name: string; display_name: string; tenant_type?: string; slug?: string },
) {
  const response = await request<{
    tenant_id: number;
    clinic_id: number;
    slug: string;
    legal_name: string;
    display_name: string;
    tenant_type: string;
    status: string;
  }>("/admin/tenants", {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function getTenant(id: number) {
  const response = await request<import("@/lib/types-admin").TenantDetail>(`/admin/tenants/${id}`);
  return response.data;
}

export async function updateTenant(
  csrfToken: string,
  id: number,
  payload: { legal_name?: string; display_name?: string; status?: string },
) {
  const response = await request(`/admin/tenants/${id}`, {
    method: "PUT",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function getTenantBranding(id: number) {
  const response = await request<import("@/lib/types-admin").TenantBranding>(
    `/admin/tenants/${id}/branding`,
  );
  return response.data;
}

export async function updateTenantBranding(
  csrfToken: string,
  id: number,
  payload: Partial<import("@/lib/types-admin").TenantBranding>,
) {
  const response = await request<import("@/lib/types-admin").TenantBranding>(
    `/admin/tenants/${id}/branding`,
    {
      method: "PUT",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function getTenantIntegrations(id: number) {
  const response = await request<import("@/lib/types-admin").TenantIntegrations>(
    `/admin/tenants/${id}/integrations`,
  );
  return response.data;
}

export async function updateTenantIntegrations(
  csrfToken: string,
  id: number,
  payload: Partial<import("@/lib/types-admin").TenantIntegrations>,
) {
  const response = await request<import("@/lib/types-admin").TenantIntegrations>(
    `/admin/tenants/${id}/integrations`,
    {
      method: "PUT",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function getTenantPlan(id: number) {
  const response = await request<import("@/lib/types-admin").TenantPlanData>(
    `/admin/tenants/${id}/plan`,
  );
  return response.data;
}

export async function updateTenantPlan(
  csrfToken: string,
  id: number,
  payload: { billing_plan?: string; ai_limit_month?: number; user_limit?: number },
) {
  const response = await request<import("@/lib/types-admin").TenantPlanData>(
    `/admin/tenants/${id}/plan`,
    {
      method: "PUT",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function getAiMetrics(filters: AiMetricsFilters = {}) {
  const params = new URLSearchParams();
  if (filters.status?.trim()) {
    params.set("status", filters.status.trim());
  }
  if (typeof filters.days === "number") {
    params.set("days", String(filters.days));
  }
  if (typeof filters.limit === "number") {
    params.set("limit", String(filters.limit));
  }
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await request<AiAuditData>(`/admin/ai-metrics${query}`);
  return response.data;
}

/**
 * Sprint 3 Page-Migration: `?paginated=1` route — `recent_logs` vira
 * envelope `Paginated<AiAuditLog>`. Sumario continua no shape original.
 */
export type AiAuditPaginatedData = {
  summary: AiAuditData["summary"];
  recent_logs: Paginated<AiAuditLog>;
  filters?: AiAuditData["filters"] & { offset?: number };
};

export async function getAiAudit(filters: AiMetricsFilters & {
  offset?: number;
  include_total?: boolean;
} = {}): Promise<AiAuditPaginatedData> {
  const params = new URLSearchParams();
  params.set("paginated", "1");
  if (filters.status?.trim()) params.set("status", filters.status.trim());
  if (typeof filters.days === "number") params.set("days", String(filters.days));
  if (typeof filters.limit === "number") params.set("limit", String(filters.limit));
  if (typeof filters.offset === "number")
    params.set("offset", String(filters.offset));
  if (filters.include_total) params.set("include_total", "1");
  const response = await request<AiAuditPaginatedData>(
    `/admin/ai-metrics?${params.toString()}`,
  );
  return response.data;
}

// ── Payments ──
export async function listPayments(params: { status?: string; patient_id?: number; limit?: number; offset?: number } = {}) {
  const sp = new URLSearchParams();
  if (params.status) sp.set("status", params.status);
  if (params.patient_id != null) sp.set("patient_id", String(params.patient_id));
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.offset != null) sp.set("offset", String(params.offset));
  const query = sp.toString() ? `?${sp.toString()}` : "";
  return request<import("@/lib/types").PaymentRequest[]>(`/payments${query}`);
}

export async function getPaymentSummary() {
  const response = await request<import("@/lib/types").PaymentSummary>("/payments/summary");
  return response.data;
}

export async function getPaymentDetail(id: number) {
  const response = await request<import("@/lib/types").PaymentDetail>(`/payments/${id}`);
  return response.data;
}

export async function issuePixCharge(
  csrfToken: string,
  payload: {
    amount_cents: number;
    description?: string;
    patient_id?: number;
    prescription_id?: number;
    pix_key?: string;
    merchant_name?: string;
    merchant_city?: string;
    expiration_hours?: number;
  },
) {
  const response = await request<import("@/lib/types").PaymentRequest>("/payments/pix", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
  return response.data;
}

export async function confirmPaymentManual(
  csrfToken: string,
  id: number,
  payload: { amount_cents?: number; payer_name?: string; payer_document?: string } = {},
) {
  const response = await request<import("@/lib/types").PaymentRequest>(
    `/payments/${id}/confirm`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify(payload),
    },
  );
  return response.data;
}

export async function cancelPayment(csrfToken: string, id: number) {
  const response = await request<import("@/lib/types").PaymentRequest>(
    `/payments/${id}/cancel`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({}),
    },
  );
  return response.data;
}

// ── Patient Portal ──
export async function getPatientProfile() {
  return request<Record<string, unknown>>("/patient/profile");
}
export async function getPatientTreatment() {
  return request<Record<string, unknown>>("/patient/treatment");
}
export async function submitDiaryEntry(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/patient/diary", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}
export async function getDiaryHistory(days?: number) {
  const qs = days ? `?days=${days}` : "";
  return request<Record<string, unknown>>(`/patient/diary${qs}`);
}
export async function getPatientEvolution() {
  return request<Record<string, unknown>>("/patient/evolution");
}
export async function getPatientAppointments() {
  return request<Record<string, unknown>>("/patient/appointments");
}

// ── Returns ──
export async function listReturns() {
  return request<Record<string, unknown>>("/returns");
}

// ── Org Management ──
export async function getOrgDashboard() {
  return request<Record<string, unknown>>("/org/dashboard");
}
export async function listOrgPatients(params?: { search?: string; status?: string; page?: number; page_size?: number }) {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.status) qs.set("status", params.status);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request<Record<string, unknown>>(`/org/patients${q ? `?${q}` : ""}`);
}
export async function listOrgDoctors() {
  return request<Record<string, unknown>>("/org/doctors");
}
export async function getOrgStock() {
  return request<Record<string, unknown>>("/org/stock");
}
export async function getOrgBilling() {
  return request<Record<string, unknown>>("/org/billing");
}
export async function getOrgFinancial() {
  return request<Record<string, unknown>>("/org/financial");
}

// ── Admin Users ──
export async function listAdminUsers(params?: { search?: string; role?: string }) {
  const qs = new URLSearchParams();
  if (params?.search) qs.set("search", params.search);
  if (params?.role) qs.set("role", params.role);
  const q = qs.toString();
  const response = await request<Record<string, unknown>[]>(`/admin/users/${q ? `?${q}` : ""}`);
  return { data: response.data, meta: response.meta };
}
export async function createAdminUser(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/admin/users/", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}
export async function updateAdminUser(userId: number, csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/admin/users/${userId}`, {
    method: "PATCH",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}

// ── Campaigns ──
export async function listCampaignTemplates() {
  const response = await request<Record<string, unknown>[]>("/campaigns/templates");
  return response.data;
}
export async function listCampaignExecutions() {
  const response = await request<Record<string, unknown>[]>("/campaigns/executions");
  return response.data;
}
export async function createCampaignTemplate(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/campaigns/templates", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}
export async function activateCampaignTemplate(id: number, csrfToken: string) {
  return request<Record<string, unknown>>(`/campaigns/templates/${id}/status`, {
    method: "PATCH",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ status: "active" }),
  });
}
export async function sendCampaign(templateId: number, csrfToken: string) {
  return request<Record<string, unknown>>(`/campaigns/templates/${templateId}/send`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({}),
  });
}

// ── Admin Dashboard ──
export async function getAdminStats() {
  const [tenants, users, ai] = await Promise.all([
    request<Record<string, unknown>[]>("/admin/tenants"),
    request<Record<string, unknown>[]>("/admin/users/"),
    request<Record<string, unknown>>("/admin/ai-metrics"),
  ]);
  return {
    total_tenants: (tenants.data ?? []).length,
    total_users: (users.data ?? []).length,
    ai_data: ai.data,
  };
}

// ── Clinical Intelligence ──
export async function getClinicalIntelligence() {
  return request<Record<string, unknown>>("/clinical/intelligence");
}
export async function getBotanicalAnalysis() {
  return request<Record<string, unknown>>("/clinical/botanical");
}
export async function getLabAnalysis(patientId?: number) {
  const qs = patientId ? `?patient_id=${patientId}` : "";
  return request<Record<string, unknown>>(`/clinical/lab${qs}`);
}
export async function getClinicalTrials() {
  return request<Record<string, unknown>>("/clinical/trials");
}

// ── Org Config, Reports, Compliance ──
export async function getClinicConfig() {
  return request<Record<string, unknown>>("/org/config");
}
export async function updateClinicConfig(csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>("/org/config", {
    method: "PATCH",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}
export async function getOrgReports(period?: string) {
  const qs = period ? `?period=${period}` : "";
  return request<Record<string, unknown>>(`/org/reports${qs}`);
}
export async function getOrgCompliance() {
  return request<Record<string, unknown>>("/org/compliance");
}

// ── Regulatory/Legislation ──
export async function listLegislationFiles() {
  const response = await request<Record<string, unknown>[]>("/regulatory/files");
  return response.data;
}
export async function uploadLegislation(csrfToken: string) {
  return request<Record<string, unknown>>("/regulatory/upload", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({}),
  });
}
export async function queryLegislation(csrfToken: string, question: string, options?: { files?: string[]; structured?: boolean }) {
  return request<Record<string, unknown>>("/regulatory/query", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ question, files: options?.files, structured: options?.structured }),
  });
}

// ── Knowledge Base ──
export async function getKnowledgeCatalog(params?: {
  doc_type?: string; source?: string; status?: string; search?: string; page?: number; page_size?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.doc_type) qs.set("doc_type", params.doc_type);
  if (params?.source) qs.set("source", params.source);
  if (params?.status) qs.set("status", params.status);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.page_size) qs.set("page_size", String(params.page_size));
  const q = qs.toString();
  return request<Record<string, unknown>[]>(`/knowledge/catalog${q ? `?${q}` : ""}`);
}
export async function triggerAutoSearch(csrfToken: string, terms?: string[], maxPerTerm?: number) {
  return request<Record<string, unknown>>("/knowledge/auto-search", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ terms, max_per_term: maxPerTerm }),
  });
}
export async function searchPubMed(csrfToken: string, query: string, maxResults?: number) {
  return request<Record<string, unknown>>("/knowledge/search-pubmed", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ query, max_results: maxResults }),
  });
}
export async function getKnowledgeStats() {
  return request<Record<string, unknown>>("/knowledge/stats");
}
export async function deleteKnowledgeCatalogItem(id: number, csrfToken: string) {
  return request<{ deleted: boolean; id: number }>(`/knowledge/catalog/${id}`, {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({}),
  });
}

// ── Knowledge Monitors ──
export async function getKnowledgeMonitors() {
  const response = await request<Record<string, unknown>[]>("/knowledge/monitors");
  return response.data;
}
export async function createKnowledgeMonitor(csrfToken: string, payload: { name: string; url: string; source_type: string; search_query?: string; check_interval_hours?: number }) {
  return request<Record<string, unknown>>("/knowledge/monitors", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}
export async function toggleKnowledgeMonitor(id: number, csrfToken: string, isActive: boolean) {
  return request<Record<string, unknown>>(`/knowledge/monitors/${id}`, {
    method: "PATCH",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({ is_active: isActive }),
  });
}
export async function runKnowledgeMonitors(csrfToken: string) {
  return request<Record<string, unknown>>("/knowledge/monitors/run", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({}),
  });
}

// ── Conversations (Inbox) ──
/**
 * Sprint 3 Page-Migration: envelope `Paginated<Conversation>`. Use
 * `.items` no consumer e `.has_more` para "carregar mais".
 */
export async function listConversations(params?: {
  status?: string;
  search?: string;
  limit?: number;
  offset?: number;
  include_total?: boolean;
}): Promise<Paginated<Conversation>> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.search) qs.set("search", params.search);
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.include_total) qs.set("include_total", "1");
  const q = qs.toString();
  const response = await request<Paginated<Conversation>>(
    `/conversations${q ? `?${q}` : ""}`,
  );
  return response.data;
}
export async function getConversation(id: number, limit?: number) {
  const qs = limit ? `?limit=${limit}` : "";
  const response = await request<import("@/lib/types").ConversationDetail>(`/conversations/${id}${qs}`);
  return response.data;
}
export async function sendConversationMessage(id: number, csrfToken: string, message: string) {
  const response = await request<{ message_id: number; sent_via_whatsapp: boolean }>(
    `/conversations/${id}/messages`,
    {
      method: "POST",
      headers: { "X-CSRF-Token": csrfToken },
      body: JSON.stringify({ message }),
    },
  );
  return response.data;
}
export async function markConversationRead(id: number, csrfToken: string) {
  return request<{ marked: boolean }>(`/conversations/${id}/read`, {
    method: "PATCH",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify({}),
  });
}
export async function getUnreadCount() {
  const response = await request<{ unread_count: number }>("/conversations/unread");
  return response.data;
}

// ── Acompanhamento (cuidado continuo) ──
export type AcompanhamentoKpis = {
  patients_at_risk: number;
  followups_pending: number;
  triages_in_progress: number;
  adverse_events_open: number;
};

export type AcompanhamentoAgentActivity = {
  agent: "Triagem" | "Anamnese" | "FollowUp" | "Regulatorio";
  actions: number;
  last_action_at: string | null;
};

export type AcompanhamentoOverview = {
  tenant_id: number;
  generated_at: string;
  kpis: AcompanhamentoKpis;
  agents_activity_24h: AcompanhamentoAgentActivity[];
};

export async function getAcompanhamentoOverview() {
  const response = await request<AcompanhamentoOverview>(
    "/org/acompanhamento/overview",
  );
  return response.data;
}

export type ActivePatient = {
  patient_id: number;
  patient_name: string;
  patient_phone: string | null;
  plan_name: string | null;
  dosage: string | null;
  frequency: string | null;
  plan_started_at: string | null;
  days_in_treatment: number;
  next_return_date: string | null;
  next_return_in_days: number | null;
  followup_status: string | null;
  followup_type: string | null;
  last_contact_at: string | null;
};

export async function getAcompanhamentoActivePatients(limit: number = 20) {
  const response = await request<{ items: ActivePatient[]; count: number }>(
    `/org/acompanhamento/active-patients?limit=${limit}`,
  );
  return response.data;
}

// ── Agent Management ──
export async function listAgents() {
  const response = await request<Record<string, unknown>[]>("/admin/agents/");
  return response.data;
}
export async function getAgentDiary(agentName: string, lastN?: number) {
  const qs = lastN ? `?last_n=${lastN}` : "";
  const response = await request<Record<string, unknown>[]>(`/admin/agents/${agentName}/diary${qs}`);
  return response.data;
}
export async function getAgentSkills(agentName: string) {
  return request<Record<string, unknown>>(`/admin/agents/${agentName}/skills`);
}
export async function executeAgent(agentName: string, csrfToken: string, payload: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/admin/agents/${agentName}/execute`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
}

/* ---------------------------------------------------------------------------
 * Medical onboarding (Sprint C MVP)
 * ------------------------------------------------------------------------- */

export interface MedicalProfileData {
  full_name: string;
  crm: string;
  specialty: string;
  photo_url: string | null;
  crm_doc_url: string | null;
  diploma_url: string | null;
  prefs_notifications: boolean;
  prefs_ai_level: string;
  onboarding_completed_at: string | null;
}

export async function getMedicalOnboarding() {
  const response = await request<MedicalProfileData>("/med/onboarding");
  return response.data;
}

export async function completeMedicalOnboarding(
  csrfToken: string,
  payload: Partial<MedicalProfileData>,
) {
  const response = await request<MedicalProfileData>("/med/onboarding/complete", {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    body: JSON.stringify(payload),
  });
  return response.data;
}
