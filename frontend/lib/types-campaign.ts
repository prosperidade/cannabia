/* ─── Campaign types ─────────────────────────────────────────────────
   Espelham as rotas em src/web/routes/campaigns.py.
   Consumidos pelas páginas de campanhas WhatsApp / Email / SMS.
   ──────────────────────────────────────────────────────────────────── */

// ── Enums ──────────────────────────────────────────────────────────

export type CampaignChannel = "whatsapp" | "email" | "sms";

export type CampaignTemplateStatus = "draft" | "active" | "archived";

export type CampaignExecutionStatus = "pending" | "in_progress" | "completed" | "failed";

// ── Template ───────────────────────────────────────────────────────

export type CampaignTemplate = {
  id: number;
  clinic_id: number;
  name: string;
  /** Corpo do template com variáveis (ex: {{patient_name}}). */
  template_body: string;
  channel: CampaignChannel;
  /** Descrição opcional do template. */
  description: string | null;
  status: CampaignTemplateStatus;
  created_by: number;
  created_at: string;
};

/** Payload para criação de template (POST /api/v1/campaigns/templates). */
export type CampaignTemplatePayload = {
  name: string;
  template_body: string;
  channel?: CampaignChannel;
  description?: string;
};

/** Payload para atualização de status (PATCH .../status). */
export type CampaignTemplateStatusPayload = {
  status: CampaignTemplateStatus;
};

// ── Execution (Disparo) ────────────────────────────────────────────

export type CampaignExecution = {
  id: number;
  template_id: number;
  clinic_id: number;
  status: CampaignExecutionStatus;
  /** Total de pacientes selecionados para o disparo. */
  total_patients: number;
  /** Quantidade enviada com sucesso até o momento. */
  sent_count: number;
  /** Quantidade de envios falhados. */
  failed_count: number;
  /** user_id que disparou a campanha. */
  triggered_by: number;
  started_at: string;
  completed_at: string | null;
};

/** Payload para disparo de campanha (POST .../send). */
export type CampaignSendPayload = {
  /** IDs dos pacientes alvo. Se omitido, envia para todos elegíveis. */
  patient_ids?: number[];
};

// ── API response wrappers ──────────────────────────────────────────

export type CampaignListMeta = {
  count: number;
};

export type CampaignTemplateListResponse = {
  data: CampaignTemplate[];
  meta: CampaignListMeta;
};

export type CampaignExecutionListResponse = {
  data: CampaignExecution[];
  meta: CampaignListMeta;
};
