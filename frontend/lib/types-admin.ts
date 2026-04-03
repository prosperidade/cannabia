/* ─── Admin / Tenant types ───────────────────────────────────────────
   Espelham as rotas que o backend vai expor na Fase 5 (5.2 + 5.3).
   Enquanto os endpoints não existem, o frontend usa mock data.
   ──────────────────────────────────────────────────────────────────── */

export type TenantStatus = "active" | "suspended" | "trial" | "cancelled";

export type TenantPlan = "starter" | "professional" | "enterprise";

export type Tenant = {
  id: number;
  name: string;
  slug: string;
  status: TenantStatus;
  plan: TenantPlan;
  clinic_count: number;
  user_count: number;
  ai_executions_month: number;
  ai_limit_month: number;
  created_at: string;
  trial_ends_at: string | null;
};

export type TenantDetail = Tenant & {
  clinics: TenantClinic[];
  owner: TenantUser | null;
  billing: TenantBilling | null;
};

export type TenantClinic = {
  id: number;
  name: string;
  patient_count: number;
  status: "active" | "inactive";
};

export type TenantUser = {
  id: number;
  username: string;
  email: string;
  role: string;
};

export type TenantBilling = {
  plan: TenantPlan;
  price_brl: number;
  next_billing_date: string;
  usage_pct: number;
};

export type SystemHealthSummary = {
  total_tenants: number;
  active_tenants: number;
  total_clinics: number;
  total_users: number;
  ai_executions_today: number;
  system_status: "healthy" | "degraded" | "unhealthy";
};
