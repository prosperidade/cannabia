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
  tenant_type?: string;
  legal_name?: string;
  clinics?: TenantClinic[];
  owner?: TenantUser | null;
  billing?: TenantBilling | null;
  clinic_count?: number;
  user_count?: number;
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

export type TenantBranding = {
  tenant_id: number;
  brand_name: string | null;
  logo_url: string | null;
  primary_color: string | null;
  secondary_color: string | null;
  subdomain: string | null;
  updated_at?: string;
};

export type TenantIntegrations = {
  tenant_id: number;
  whatsapp_phone_number_id: string | null;
  whatsapp_business_account_id: string | null;
  meta_whatsapp_key: string | null;
  whatsapp_app_secret: string | null;
  verify_token: string | null;
  email_from: string | null;
  smtp_server: string | null;
  smtp_port: number | null;
  email_password: string | null;
  doctor_email: string | null;
  ai_provider: string | null;
  ai_api_key: string | null;
  openai_api_key: string | null;
};

export type TenantPlanData = {
  tenant_id: number;
  billing_plan: TenantPlan;
  ai_executions_month: number;
  ai_limit_month: number;
  user_limit: number;
  quota_reset_at?: string | null;
};

export type SystemHealthSummary = {
  total_tenants: number;
  active_tenants: number;
  total_clinics: number;
  total_users: number;
  ai_executions_today: number;
  system_status: "healthy" | "degraded" | "unhealthy";
};
