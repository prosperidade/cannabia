/* ─── Medical / AI Pipeline types ────────────────────────────────────
   Espelham os schemas Pydantic em src/ai/schemas.py.
   Consumidos pelo Cockpit do Médico (/medico/triagem-dashboard).
   ──────────────────────────────────────────────────────────────────── */

// ── Agent 3 Pipeline Output ─────────────────────────────────────────

export type RiskLevel = "baixo" | "moderado" | "alto" | "critico";

export type ClinicalAnalysis = {
  probable_conditions: string[];
  risk_level: RiskLevel;
  recommended_exams: string[];
  red_flags: string[];
};

export type TreatmentPlan = {
  cannabinoid_ratio: string;
  suggested_dosage: string;
  administration_route: string;
  monitoring_plan: string;
  precautions: string[];
};

export type ScientificReport = {
  summary: string;
  supporting_evidence: string[];
  references: string[];
};

export type PipelineResult = {
  clinical_analysis: ClinicalAnalysis;
  treatment_plan: TreatmentPlan;
  scientific_report: ScientificReport;
  rag_chunks_used: number;
  report_model: string;
  token_usage: { input: number; output: number; total: number };
};

// ── Triage Agent Schemas ────────────────────────────────────────────

export type ConfidenceLevel = "alto" | "medio" | "baixo";

export type ExtractedCondition = {
  condition_name: string;
  icd10_hint: string | null;
  confidence: ConfidenceLevel;
  evidence_snippet: string;
};

// ── Biometry / Vital Signs ──────────────────────────────────────────

export type VitalSigns = {
  bp_systolic: number | null;
  bp_diastolic: number | null;
  heart_rate: number | null;
  temperature: number | null;
  spo2: number | null;
  respiratory_rate: number | null;
  weight_kg: number | null;
  height_cm: number | null;
  bmi: number | null;
  pain_level: number | null;
};

// ── Patient Context ─────────────────────────────────────────────────

export type PatientContext = {
  id: number;
  name: string;
  age: number;
  main_complaint: string;
  symptoms: string[];
  current_medications: string[];
  allergies: string[];
  medical_history: string | null;
};

// ── Prescription (Receita Eletrônica) ───────────────────────────────

export type PrescriptionType = "branca" | "azul";

export type PrescriptionItem = {
  medication: string;
  concentration: string;
  dosage: string;
  route: string;
  frequency: string;
  duration: string;
  instructions: string;
};

export type PrescriptionData = {
  type: PrescriptionType;
  patient_name: string;
  patient_cpf: string;
  prescriber_name: string;
  prescriber_crm: string;
  prescriber_uf: string;
  date: string;
  items: PrescriptionItem[];
  notes: string;
};

// ── Full Triagem Dashboard Payload ──────────────────────────────────

export type TriagemDashboardData = {
  patient: PatientContext;
  vitals: VitalSigns;
  pipeline: PipelineResult;
  extracted_conditions: ExtractedCondition[];
  prescription_draft: Partial<PrescriptionData> | null;
};
