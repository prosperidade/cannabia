/**
 * Governance Hub API client — F1.7 do docs/BACKLOG_SCC.md.
 *
 * Wrappers tipados sobre /api/v1/governance. Utiliza o request compartilhado
 * de lib/api.ts.
 */

import { request } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type AssociationRecord = {
  tenant_id: number;
  statute_document_id: number | null;
  directive_board: Array<Record<string, unknown>>;
  members_count: number;
  is_judicial_operation: boolean;
  judicial_authorization: string | null;
  sandbox_application_status: string | null;
  eligibility_validated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type InstitutionalDocument = {
  id: number;
  tenant_id: number;
  document_type: string;
  title: string;
  version: string;
  file_uri: string;
  file_hash: string;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  uploaded_by: number | null;
  created_at: string;
};

export type TechnicalResponsible = {
  id: number;
  tenant_id: number;
  user_id: number | null;
  full_name: string;
  professional_council: string;
  council_number: string;
  council_state: string;
  habilitation_valid_until: string | null;
  document_ids: number[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CapacityAssessment = {
  id: number;
  tenant_id: number;
  assessment_date: string;
  infrastructure_score: Record<string, unknown>;
  human_resources_score: Record<string, unknown>;
  process_maturity_score: Record<string, unknown>;
  proposed_scale: Record<string, unknown>;
  overall_readiness: number | null;
  assessed_by: number | null;
  created_at: string;
};

export type EligibilityFindingStatus = "pass" | "fail" | "warn";

export type EligibilityFinding = {
  code: string;
  status: EligibilityFindingStatus;
  message: string;
  details: Record<string, unknown>;
};

export type EligibilityReport = {
  tenant_id: number;
  checked_at: string;
  is_eligible: boolean;
  has_warnings: boolean;
  findings: EligibilityFinding[];
};

export type DossierPayload = {
  tenant_id: number;
  template_version: string;
  generated_at: string;
  is_eligible: boolean;
  fail_count: number;
  warn_count: number;
  markdown: string;
  findings: EligibilityFinding[];
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function csrfHeader(token: string): HeadersInit {
  return { "X-CSRF-Token": token };
}

/* ------------------------------------------------------------------ */
/*  Association                                                        */
/* ------------------------------------------------------------------ */

export async function getAssociation() {
  const response = await request<{ association: AssociationRecord | null }>(
    "/governance/association",
  );
  return response.data.association;
}

export type AssociationPayload = {
  members_count: number;
  directive_board?: Array<Record<string, unknown>>;
  is_judicial_operation?: boolean;
  judicial_authorization?: string | null;
  statute_document_id?: number | null;
};

export async function upsertAssociation(csrfToken: string, payload: AssociationPayload) {
  const response = await request<{ association: AssociationRecord }>(
    "/governance/association",
    {
      method: "PUT",
      headers: csrfHeader(csrfToken),
      body: JSON.stringify(payload),
    },
  );
  return response.data.association;
}

/* ------------------------------------------------------------------ */
/*  Institutional Documents                                            */
/* ------------------------------------------------------------------ */

export async function listDocuments(opts?: { type?: string; activeOnly?: boolean }) {
  const params = new URLSearchParams();
  if (opts?.type) params.set("type", opts.type);
  if (opts?.activeOnly === false) params.set("active_only", "false");
  const qs = params.toString() ? `?${params}` : "";
  const response = await request<{ documents: InstitutionalDocument[] }>(
    `/governance/documents${qs}`,
  );
  return response.data.documents;
}

export type DocumentCreatePayload = {
  document_type: string;
  title: string;
  version: string;
  file_uri: string;
  file_hash: string;
  valid_from: string;
  valid_until?: string | null;
};

export async function createDocument(csrfToken: string, payload: DocumentCreatePayload) {
  const response = await request<{ document: InstitutionalDocument }>(
    "/governance/documents",
    {
      method: "POST",
      headers: csrfHeader(csrfToken),
      body: JSON.stringify(payload),
    },
  );
  return response.data.document;
}

export async function deactivateDocument(csrfToken: string, docId: number) {
  await request<{ deactivated: true; document_id: number }>(
    `/governance/documents/${docId}`,
    {
      method: "DELETE",
      headers: csrfHeader(csrfToken),
    },
  );
}

/* ------------------------------------------------------------------ */
/*  Technical Responsibles                                             */
/* ------------------------------------------------------------------ */

export async function listTechnicalResponsibles(activeOnly = true) {
  const qs = activeOnly ? "" : "?active_only=false";
  const response = await request<{ technical_responsibles: TechnicalResponsible[] }>(
    `/governance/rts${qs}`,
  );
  return response.data.technical_responsibles;
}

export type RtCreatePayload = {
  full_name: string;
  professional_council: string;
  council_number: string;
  council_state: string;
  habilitation_valid_until?: string | null;
  document_ids?: number[];
  user_id?: number | null;
};

export async function createTechnicalResponsible(
  csrfToken: string,
  payload: RtCreatePayload,
) {
  const response = await request<{ technical_responsible: TechnicalResponsible }>(
    "/governance/rts",
    {
      method: "POST",
      headers: csrfHeader(csrfToken),
      body: JSON.stringify(payload),
    },
  );
  return response.data.technical_responsible;
}

export async function updateTechnicalResponsible(
  csrfToken: string,
  rtId: number,
  fields: Partial<RtCreatePayload & { is_active: boolean }>,
) {
  const response = await request<{ technical_responsible: TechnicalResponsible }>(
    `/governance/rts/${rtId}`,
    {
      method: "PATCH",
      headers: csrfHeader(csrfToken),
      body: JSON.stringify(fields),
    },
  );
  return response.data.technical_responsible;
}

export async function deactivateTechnicalResponsible(csrfToken: string, rtId: number) {
  await request<{ deactivated: true; rt_id: number }>(`/governance/rts/${rtId}`, {
    method: "DELETE",
    headers: csrfHeader(csrfToken),
  });
}

/* ------------------------------------------------------------------ */
/*  Capacity Assessments                                               */
/* ------------------------------------------------------------------ */

export async function getLatestCapacityAssessment() {
  const response = await request<{ capacity_assessment: CapacityAssessment | null }>(
    "/governance/capacity/latest",
  );
  return response.data.capacity_assessment;
}

export type CapacityCreatePayload = {
  assessment_date?: string;
  infrastructure_score: Record<string, unknown>;
  human_resources_score: Record<string, unknown>;
  process_maturity_score: Record<string, unknown>;
  proposed_scale: Record<string, unknown>;
  overall_readiness?: number | null;
};

export async function createCapacityAssessment(
  csrfToken: string,
  payload: CapacityCreatePayload,
) {
  const response = await request<{ capacity_assessment: CapacityAssessment }>(
    "/governance/capacity",
    {
      method: "POST",
      headers: csrfHeader(csrfToken),
      body: JSON.stringify(payload),
    },
  );
  return response.data.capacity_assessment;
}

/* ------------------------------------------------------------------ */
/*  Eligibility + Dossier                                              */
/* ------------------------------------------------------------------ */

export async function getEligibility() {
  const response = await request<EligibilityReport>("/governance/eligibility");
  return response.data;
}

export async function refreshEligibility(csrfToken: string) {
  const response = await request<EligibilityReport>(
    "/governance/eligibility/refresh",
    {
      method: "POST",
      headers: csrfHeader(csrfToken),
    },
  );
  return response.data;
}

export async function getDossier() {
  const response = await request<DossierPayload>(
    "/governance/eligibility/dossier",
  );
  return response.data;
}
