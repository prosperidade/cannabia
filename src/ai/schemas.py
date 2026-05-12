from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Literal, Optional


class AnamnesisInput(BaseModel):
    patient_name: str
    age: int
    main_complaint: str
    symptoms: List[str]
    current_medications: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    medical_history: Optional[str] = None
    weight_kg: Optional[float] = Field(default=None, ge=1.0, le=300.0)
    height_cm: Optional[float] = Field(default=None, ge=30.0, le=250.0)
    prior_cannabis_use: Optional[bool] = None


class ClinicalAnalysis(BaseModel):
    probable_conditions: List[str]
    risk_level: str
    recommended_exams: List[str]
    red_flags: List[str]


class TreatmentPlan(BaseModel):
    cannabinoid_ratio: str
    suggested_dosage: str
    administration_route: str
    monitoring_plan: str
    precautions: List[str]


class ScientificReport(BaseModel):
    summary: str
    supporting_evidence: List[str]
    references: List[str]
    # Sprint 3 Track CFD — explicabilidade: qual input alimentou o query RAG.
    # Optional pra back-compat com reports persistidos antes da Sprint 3.
    based_on: Optional[Literal["final_dosage", "treatment_plan"]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# TRIAGE AGENT — Widget-driven response schemas
# O frontend B2B2C renderiza "Nano-Apps" (widgets) com base no tipo injetado.
# ═══════════════════════════════════════════════════════════════════════════════

class WidgetType(str, Enum):
    """Tipos de widget que o frontend sabe renderizar."""
    PHYSICAL_DATA_SLIDER = "PHYSICAL_DATA_SLIDER"
    PAIN_SCALE = "PAIN_SCALE"
    SYMPTOM_CHECKLIST = "SYMPTOM_CHECKLIST"
    MEDICATION_SELECTOR = "MEDICATION_SELECTOR"
    ALLERGY_TAGS = "ALLERGY_TAGS"
    VITAL_SIGNS = "VITAL_SIGNS"
    DOSAGE_CALCULATOR = "DOSAGE_CALCULATOR"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    APPOINTMENT_SCHEDULER = "APPOINTMENT_SCHEDULER"
    TEXT_ONLY = "TEXT_ONLY"


class ExtractedCondition(BaseModel):
    """Patologia extraída do relato livre do paciente."""
    condition_name: str = Field(description="Nome da condição/patologia identificada")
    icd10_hint: Optional[str] = Field(
        default=None,
        description="Código CID-10 aproximado, se identificável",
    )
    confidence: str = Field(description="alto, medio ou baixo")
    evidence_snippet: str = Field(
        description="Trecho do relato do paciente que sustenta esta extração",
    )


class TriageResponse(BaseModel):
    """
    Resposta estruturada do Agente de Triagem.

    O frontend consome este schema para:
      1. Exibir `message` como texto humanizado no chat.
      2. Renderizar o widget indicado por `inject_widget`.
      3. Popular o widget com os valores de `data`.
      4. Mostrar `extracted_conditions` no painel clínico lateral.
    """
    message: str = Field(
        description=(
            "Mensagem empática e profissional para o paciente, "
            "reconhecendo o relato e instruindo sobre o widget exibido"
        ),
    )
    inject_widget: WidgetType = Field(
        description="Tipo de widget que o frontend deve renderizar",
    )
    data: Dict[str, Any] = Field(
        description=(
            "Payload de dados para popular o widget. "
            "As chaves dependem do widget_type escolhido"
        ),
    )
    extracted_conditions: List[ExtractedCondition] = Field(
        default_factory=list,
        description="Patologias extraídas do relato do paciente via raciocínio clínico",
    )
    follow_up_question: Optional[str] = Field(
        default=None,
        description="Pergunta de follow-up para continuar a anamnese, se necessário",
    )


# ── OpenAI Function Calling tool definition ──────────────────────────────────
# Usado por `chains.py` para forçar structured output via `tools` parameter.

TRIAGE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "render_triage_widget",
        "description": (
            "Analisa o relato do paciente, extrai patologias, e retorna "
            "uma resposta estruturada com widget para o frontend renderizar."
        ),
        "parameters": {
            "type": "object",
            "required": ["message", "inject_widget", "data", "extracted_conditions"],
            "properties": {
                "message": {
                    "type": "string",
                    "description": (
                        "Mensagem empática para o paciente reconhecendo o relato "
                        "e instruindo sobre o widget exibido"
                    ),
                },
                "inject_widget": {
                    "type": "string",
                    "enum": [w.value for w in WidgetType],
                    "description": "Tipo de widget que o frontend deve renderizar",
                },
                "data": {
                    "type": "object",
                    "description": (
                        "Payload para popular o widget. Exemplos por tipo: "
                        "PHYSICAL_DATA_SLIDER → {suggested_weight, suggested_height, bmi_estimate}; "
                        "PAIN_SCALE → {suggested_level, body_region}; "
                        "SYMPTOM_CHECKLIST → {suggested_symptoms: [...]}; "
                        "MEDICATION_SELECTOR → {suggested_medications: [...]}; "
                        "ALLERGY_TAGS → {suggested_allergies: [...]}; "
                        "VITAL_SIGNS → {suggested_bp_systolic, suggested_bp_diastolic, suggested_heart_rate}; "
                        "DOSAGE_CALCULATOR → {cannabinoid_ratio, suggested_mg}; "
                        "DOCUMENT_UPLOAD → {requested_documents: [...]}; "
                        "APPOINTMENT_SCHEDULER → {reason, urgency}; "
                        "TEXT_ONLY → {}"
                    ),
                },
                "extracted_conditions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["condition_name", "confidence", "evidence_snippet"],
                        "properties": {
                            "condition_name": {
                                "type": "string",
                                "description": "Nome da condição/patologia identificada",
                            },
                            "icd10_hint": {
                                "type": "string",
                                "description": "Código CID-10 aproximado",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["alto", "medio", "baixo"],
                            },
                            "evidence_snippet": {
                                "type": "string",
                                "description": "Trecho do relato que sustenta a extração",
                            },
                        },
                    },
                },
                "follow_up_question": {
                    "type": "string",
                    "description": "Pergunta de follow-up para continuar a anamnese",
                },
            },
        },
    },
}


# ── Gemini response_schema (subset compatível com google.genai) ──────────────

TRIAGE_GEMINI_SCHEMA = {
    "type": "object",
    "required": ["message", "inject_widget", "data", "extracted_conditions"],
    "properties": {
        "message": {"type": "string"},
        "inject_widget": {
            "type": "string",
            "enum": [w.value for w in WidgetType],
        },
        "data": {"type": "object"},
        "extracted_conditions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["condition_name", "confidence", "evidence_snippet"],
                "properties": {
                    "condition_name": {"type": "string"},
                    "icd10_hint": {"type": "string"},
                    "confidence": {
                        "type": "string",
                        "enum": ["alto", "medio", "baixo"],
                    },
                    "evidence_snippet": {"type": "string"},
                },
            },
        },
        "follow_up_question": {"type": "string"},
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# FRONTEIRA 3 — Prescriber de Dosagem + Marketplace B2B
# ═══════════════════════════════════════════════════════════════════════════════


class AdministrationRoute(str, Enum):
    """Via de administração do óleo canabinoide."""
    SUBLINGUAL = "sublingual"
    ORAL = "oral"
    TOPICO = "topico"
    INALATORIO = "inalatorio"


class ProductSpectrum(str, Enum):
    """Espectro do produto canabinoide."""
    FULL_SPECTRUM = "full_spectrum"
    BROAD_SPECTRUM = "broad_spectrum"
    ISOLADO_CBD = "isolado_cbd"


class TitrationPhase(str, Enum):
    """Fase do protocolo de titulação."""
    INICIAL = "inicial"
    AJUSTE = "ajuste"
    MANUTENCAO = "manutencao"


class OrderStatus(str, Enum):
    """Status do pedido B2B para associação parceira."""
    PENDING = "pending"
    SENT = "sent"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


# ── Input: dados clínicos para o Prescriber ────────────────────────────────

class DosageInput(BaseModel):
    """Dados clínicos necessários para cálculo de dosagem."""
    patient_name: str
    age: int = Field(ge=0, le=120)
    weight_kg: float = Field(ge=1.0, le=300.0)
    height_cm: Optional[float] = Field(default=None, ge=30.0, le=250.0)
    main_complaint: str
    symptoms: List[str] = Field(min_length=1)
    conditions: List[str] = Field(
        default_factory=list,
        description="Condições/patologias confirmadas (CID-10 ou nome clínico)",
    )
    current_medications: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    medical_history: Optional[str] = None
    prior_cannabis_use: bool = False
    risk_level: str = Field(
        default="moderado",
        description="Nível de risco clínico: baixo, moderado, alto",
    )

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        allowed = {"baixo", "moderado", "alto"}
        v_lower = v.lower().strip()
        if v_lower not in allowed:
            raise ValueError(f"risk_level deve ser um de: {allowed}")
        return v_lower


# ── Output: Recomendação de Dosagem (retorno do LLM) ──────────────────────

class TitrationStep(BaseModel):
    """Um passo do protocolo de titulação progressiva."""
    phase: TitrationPhase
    day_range: str = Field(description="Ex: 'Dias 1-3', 'Dias 4-7'")
    drops_per_dose: int = Field(ge=1, le=30)
    doses_per_day: int = Field(ge=1, le=6)
    concentration_mg_ml: float = Field(ge=0.1, le=200.0)
    total_daily_mg: float = Field(ge=0.0)
    observations: Optional[str] = None


class DosageRecommendation(BaseModel):
    """Recomendação completa de dosagem gerada pela IA."""
    cannabinoid_ratio: str = Field(
        description="Proporção CBD:THC recomendada. Ex: '20:1', '1:1', 'CBD puro'",
    )
    spectrum: ProductSpectrum
    administration_route: AdministrationRoute
    concentration_mg_ml: float = Field(
        ge=0.1, le=200.0,
        description="Concentração recomendada do produto em mg/mL",
    )
    titration_protocol: List[TitrationStep] = Field(
        min_length=1,
        description="Protocolo de titulação progressiva (mínimo fase inicial)",
    )
    max_daily_mg: float = Field(
        ge=0.1,
        description="Dose máxima diária recomendada em mg",
    )
    clinical_rationale: str = Field(
        description="Justificativa clínica baseada em evidências para esta dosagem",
    )
    contraindications: List[str] = Field(default_factory=list)
    drug_interactions: List[str] = Field(default_factory=list)
    monitoring_checkpoints: List[str] = Field(
        description="Marcos de monitoramento clínico (ex: '7 dias: avaliar tolerância')",
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confiança da recomendação (0.0 a 1.0). Abaixo de 0.6 exige revisão médica obrigatória.",
    )
    evidence_sources: List[str] = Field(
        default_factory=list,
        description="Fontes científicas que sustentam a recomendação",
    )


# ── Output do AgentePrescritor no clinical_flow ───────────────────────────

class PrescriptionResult(BaseModel):
    """Output do stage Prescritor no clinical_flow.

    Encapsula a recomendação clampada (Rules Engine + LLM + Safety Clamp) +
    telemetria de safety + flags de qualidade. Frontend consome este shape
    em paralelo a treatment_plan e scientific_report.
    """
    final_dosage: DosageRecommendation = Field(
        description="Recomendação final pós safety-clamp",
    )
    safety_clamp_applied: bool = Field(
        description="True se _clamp_recommendation cortou alguma dose do LLM",
    )
    safety_clamp_reason: Optional[str] = Field(
        default=None,
        description="Razão humanamente legível se clamp foi aplicado",
    )
    cyp450_interactions: List[str] = Field(
        default_factory=list,
        description="Warnings de interação CYP450 detectados pelo Rules Engine",
    )
    monitoring_alerts: List[str] = Field(
        default_factory=list,
        description="Contraindicações + warnings agregados para monitoramento",
    )
    rules_engine_summary: Dict[str, Any] = Field(
        description="Snapshot dos limits: max_cbd_daily_mg, max_thc_daily_mg, age_adjustment, recommended_ratio",
    )
    dosage_defaults_used: bool = Field(
        default=False,
        description="True quando weight_kg/prior_cannabis_use vieram de defaults — anamnese ainda nao coleta esses campos (ver docs/BACKLOG_AGENTE_PRESCRITOR.md)",
    )
    confidence_score: float = Field(ge=0.0, le=1.0)


# ── Prescrição formal (médico aprova e emite) ─────────────────────────────

class PrescriptionPayload(BaseModel):
    """Prescrição médica formalizada após aprovação do médico."""
    clinic_id: int
    patient_id: int
    doctor_user_id: int
    doctor_name: str
    doctor_crm: str = Field(description="CRM do médico prescritor")
    dosage_recommendation: DosageRecommendation
    custom_notes: Optional[str] = None
    validity_days: int = Field(default=180, ge=30, le=365)


# ── Pedido B2B para Associação Parceira ───────────────────────────────────

class AssociationProduct(BaseModel):
    """Produto disponível na associação parceira."""
    product_name: str
    spectrum: ProductSpectrum
    concentration_mg_ml: float
    volume_ml: float = Field(ge=5.0, le=100.0)
    cannabinoid_ratio: str
    unit_price_brl: float = Field(ge=0.0)
    association_sku: Optional[str] = None


class B2BOrderPayload(BaseModel):
    """Payload padrão para envio de pedido à API da associação parceira."""
    order_id: Optional[str] = None
    prescription_id: int
    clinic_id: int
    patient_id: int
    patient_name: str
    doctor_crm: str
    products: List[AssociationProduct] = Field(min_length=1)
    dosage_summary: str = Field(
        description="Resumo da posologia para a associação (ex: '2 gotas 3x/dia sublingual')",
    )
    cannabinoid_ratio: str
    administration_route: AdministrationRoute
    total_daily_mg: float
    treatment_duration_days: int = Field(ge=30, le=365)
    shipping_address: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None


# ── OpenAI Function Calling tool definition para Prescriber ────────────────

PRESCRIBER_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "recommend_dosage",
        "description": (
            "Analisa dados clínicos do paciente e retorna uma recomendação "
            "de dosagem canabinoide com protocolo de titulação progressiva."
        ),
        "parameters": {
            "type": "object",
            "required": [
                "cannabinoid_ratio", "spectrum", "administration_route",
                "concentration_mg_ml", "titration_protocol", "max_daily_mg",
                "clinical_rationale", "monitoring_checkpoints", "confidence_score",
            ],
            "properties": {
                "cannabinoid_ratio": {
                    "type": "string",
                    "description": "Proporção CBD:THC. Ex: '20:1', '1:1', 'CBD puro'",
                },
                "spectrum": {
                    "type": "string",
                    "enum": [s.value for s in ProductSpectrum],
                },
                "administration_route": {
                    "type": "string",
                    "enum": [r.value for r in AdministrationRoute],
                },
                "concentration_mg_ml": {
                    "type": "number",
                    "description": "Concentração recomendada em mg/mL",
                },
                "titration_protocol": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "phase", "day_range", "drops_per_dose",
                            "doses_per_day", "concentration_mg_ml", "total_daily_mg",
                        ],
                        "properties": {
                            "phase": {
                                "type": "string",
                                "enum": [p.value for p in TitrationPhase],
                            },
                            "day_range": {"type": "string"},
                            "drops_per_dose": {"type": "integer"},
                            "doses_per_day": {"type": "integer"},
                            "concentration_mg_ml": {"type": "number"},
                            "total_daily_mg": {"type": "number"},
                            "observations": {"type": "string"},
                        },
                    },
                },
                "max_daily_mg": {"type": "number"},
                "clinical_rationale": {"type": "string"},
                "contraindications": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "drug_interactions": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "monitoring_checkpoints": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence_score": {
                    "type": "number",
                    "description": "0.0 a 1.0 — confiança na recomendação",
                },
                "evidence_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    },
}
