import type {
  ApiSessionResponse,
  AppointmentItem,
  AppointmentPayload,
  AttendanceDetail,
  AttendanceListItem,
  DashboardData,
  DashboardMessage,
  MedicalRecordPayload,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5000/api/v1";

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

async function request<T>(
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

export async function listAttendances(status?: string) {
  const params = new URLSearchParams();
  if (status && status !== "all") {
    params.set("status", status);
  }
  const query = params.toString() ? `?${params}` : "";
  const response = await request<AttendanceListItem[]>(`/attendances${query}`);
  return response.data;
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

export async function listAppointments() {
  const response = await request<AppointmentItem[]>("/appointments");
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
