/* ─── Triage Wizard types ────────────────────────────────────────────
   Tipos para o wizard de triagem (intake) do paciente.
   Usado nas páginas /triagem e no chat dinâmico de intake.
   ──────────────────────────────────────────────────────────────────── */

/** Steps sequenciais do wizard de triagem. */
export type TriagemStep =
  | "motivo"
  | "sintomas"
  | "dados_fisicos"
  | "emocional"
  | "habitos"
  | "historico"
  | "revisao";

// ── Step payloads ──────────────────────────────────────────────────

export type TriagemMotivo = {
  objetivo_principal: string;
  outros_motivos?: string[];
};

export type TriagemSintoma = {
  nome: string;
  /** Escala de 0 (nenhum) a 10 (insuportável). */
  intensidade: number;
  /** Ex: "2 semanas", "3 meses". */
  duracao?: string;
  descricao_adicional?: string;
};

export type TriagemDadosFisicos = {
  peso_kg?: number;
  altura_cm?: number;
  sexo_biologico?: "masculino" | "feminino";
};

export type TriagemEstadoEmocional = {
  perde_foco: boolean;
  problemas_memoria: boolean;
  facilmente_irritado: boolean;
  problemas_estresse: boolean;
  episodios_panico: boolean;
  diagnostico_esquizofrenia_psicose: boolean;
  parente_esquizofrenia_psicose: boolean;
  diagnostico_ansiedade_depressao: boolean;
};

export type TriagemHabitos = {
  acorda_cansado: boolean;
  fuma: boolean;
  frequencia_fumo?: string;
  uso_alcool: boolean;
  ja_usou_cannabis: boolean;
  frequencia_cannabis?: string;
  /** Histórico de arritmia cardíaca — contra-indicação relativa. */
  arritmia_cardiaca: boolean;
  /** Histórico de psicose — contra-indicação absoluta para THC alto. */
  historico_psicose: boolean;
};

export type TriagemHistorico = {
  casado: boolean;
  tem_filhos: boolean;
  passou_por_aborto: boolean;
  trabalha: boolean;
  estuda: boolean;
  pratica_atividade_fisica: boolean;
};

// ── Formulário agregado ────────────────────────────────────────────

export type TriagemFormData = {
  motivo: TriagemMotivo;
  sintomas: TriagemSintoma[];
  dados_fisicos: TriagemDadosFisicos;
  estado_emocional: TriagemEstadoEmocional;
  habitos: TriagemHabitos;
  historico: TriagemHistorico;
};

// ── Estado do Wizard ───────────────────────────────────────────────

export type WizardState = {
  currentStep: TriagemStep;
  completedSteps: TriagemStep[];
  formData: Partial<TriagemFormData>;
  isSubmitting: boolean;
  error?: string;
};

// ── Chat Intake Session (REST responses from chat_intake.py) ──────

/** Estado da sessão do chat de intake (server-side). */
export type ChatSessionState = "waiting" | "active" | "completed" | "expired";

/** Resposta de POST /api/v1/chat/sessions (criação de sessão). */
export type ChatSessionCreated = {
  session_id: string;
  patient_token: string;
  state: ChatSessionState;
  created_at: string;
};

/** Resposta de POST /api/v1/chat/handshake (troca token -> session). */
export type ChatHandshakeResponse = {
  session_id: string;
  clinic_id: number;
  state: ChatSessionState;
  /** Namespace do SocketIO para conectar (ex: "/chat"). */
  ws_path: string;
};

/** Resposta de GET /api/v1/chat/metrics. */
export type ChatMetrics = {
  active_sessions: number;
  active_sessions_global: number;
};

// ── SocketIO event payloads ────────────────────────────────────────

/** Client -> Server: dados de um step do formulário. */
export type StepDataPayload = {
  session_id: string;
  step: string;
  value: unknown;
  /** Marca o campo como sensível (PII) para criptografia Fernet. */
  sensitive?: boolean;
};

/** Server -> Client: confirmação de recebimento de step. */
export type StepAckPayload = {
  step: string;
  ok: boolean;
  encrypted?: boolean;
};

/** Server -> Room da clínica: progresso do paciente. */
export type PatientProgressPayload = {
  session_id: string;
  steps_completed: number;
  last_step: string;
  encrypted?: boolean;
};
