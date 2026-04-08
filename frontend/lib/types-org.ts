/* ─── Organization / Admin types ─────────────────────────────────────
   Tipos para gestão organizacional, estoque, faturamento e perfis
   médicos. Complementam types-admin.ts com granularidade operacional.
   ──────────────────────────────────────────────────────────────────── */

// ── Dashboard Metrics ──────────────────────────────────────────────

export type OrgDashboardMetrics = {
  pacientes_ativos: number;
  consultas_mes: number;
  /** Receita do mês corrente em BRL. */
  receita_mes: number;
  /** Porcentagem de conversão lead -> paciente. */
  taxa_conversao: number;
  /** Net Promoter Score (escala -100 a +100). */
  nps: number;
};

// ── Stock / Estoque ────────────────────────────────────────────────

export type StockStatus = "available" | "low" | "expired" | "reserved";

export type StockItem = {
  id: number;
  product_name: string;
  /** Código do lote para rastreabilidade ANVISA. */
  batch_code: string;
  quantity: number;
  unit: string;
  /** Data de validade (ISO 8601 date). */
  expiry_date: string;
  status: StockStatus;
};

// ── Billing / Faturamento ──────────────────────────────────────────

export type BillingStatus = "pending" | "paid" | "overdue" | "cancelled";

export type BillingRecord = {
  id: number;
  tenant_id: number;
  /** Período de referência (ex: "2026-04"). */
  period: string;
  /** Valor em BRL. */
  amount: number;
  status: BillingStatus;
  /** Data de vencimento (ISO 8601 date). */
  due_date: string;
  /** Data de pagamento, se houver. */
  paid_at?: string | null;
};

// ── Doctor Profile ─────────────────────────────────────────────────

export type DoctorStatus = "active" | "inactive" | "suspended";

export type DoctorProfile = {
  id: number;
  name: string;
  /** Registro no Conselho Regional de Medicina. */
  crm: string;
  specialty: string;
  status: DoctorStatus;
  /** Quantidade de clínicas vinculadas ao médico. */
  clinic_count: number;
  /** Quantidade de usuários sob supervisão. */
  user_count: number;
  /** Total de execuções de IA realizadas pelo médico. */
  ai_executions: number;
};

// ── Tenant Provisioning (from tenant_admin.py) ─────────────────────

export type TenantType = "clinic" | "association" | "doctor";

/** Payload para criação de tenant (POST /api/v1/admin/tenants). */
export type CreateTenantPayload = {
  legal_name: string;
  display_name: string;
  tenant_type?: TenantType;
  slug?: string;
};

/** Resposta de criação de tenant. */
export type CreateTenantResult = {
  tenant_id: number;
  clinic_id: number;
  slug: string;
  legal_name: string;
  display_name: string;
  tenant_type: TenantType;
  status: string;
};

/** Payload para atualização de tenant (PUT /api/v1/admin/tenants/<id>). */
export type UpdateTenantPayload = {
  legal_name?: string;
  display_name?: string;
  status?: string;
};

/** Payload para convite de usuário (POST .../users). */
export type InviteUserPayload = {
  username: string;
  password: string;
  role?: "Admin" | "Medico" | "Atendente";
};

/** Resposta de convite de usuário. */
export type InviteUserResult = {
  user_id: number;
  tenant_id: number;
  clinic_id: number;
  username: string;
  role: string;
  is_new_user: boolean;
};

// ── Prescription & Order (from prescriptions.py) ───────────────────

/** Status do pedido B2B no ciclo de fulfillment. */
export type B2BOrderStatus = "pending" | "sent" | "confirmed" | "fulfilled";

/** Produto no pedido B2B. */
export type B2BOrderProduct = {
  product_id: number;
  product_name: string;
  quantity: number;
  unit: string;
};

/** Payload para criação de pedido B2B (POST .../order). */
export type CreateB2BOrderPayload = {
  products: B2BOrderProduct[];
  /** Duração do tratamento em dias (default: 90). */
  treatment_duration_days?: number;
  shipping_address?: string;
  notes?: string;
};
