# src/ai/prescriber.py
"""
Fronteira 3 — Prescriber de Dosagem Canabinoide.

Arquitetura em 2 camadas:
  1. Rules Engine (determinístico) — calcula limites farmacológicos seguros
     com base em peso, idade, condição e medicações.
  2. LLM Layer (GPT-4o-mini, temperature=0) — refina a recomendação usando
     raciocínio clínico e gera o protocolo de titulação detalhado.

O Rules Engine SEMPRE prevalece sobre o LLM para limites de segurança.
Se o LLM sugerir dose acima do limite, o Rules Engine corta automaticamente.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from src.ai.chains import (
    _run_openai,
    _RETRYABLE_OPENAI,
    cb_openai,
    CircuitOpenError,
    openai_client,
    OPENAI_MODEL,
)
from src.ai.schemas import (
    AdministrationRoute,
    DosageInput,
    DosageRecommendation,
    ProductSpectrum,
    TitrationPhase,
    TitrationStep,
    PRESCRIBER_TOOL_DEFINITION,
)
# Sprint 2 Track Reg: prompts vem do registry (DB-first com fallback
# hardcoded em src.ai.prompts). Permite override versionado via DB.
from src.ai.prompt_registry import get_prompt

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger("cannabia.prescriber")

# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA 1 — Rules Engine (Determinístico)
# Calcula limites de segurança baseados em farmacologia clínica.
# ═══════════════════════════════════════════════════════════════════════════════

# 1 gota ≈ 0.05 mL (padrão conta-gotas farmacêutico)
DROP_VOLUME_ML = 0.05


@dataclass
class SafetyLimits:
    """Limites de segurança calculados pelo Rules Engine."""
    max_cbd_daily_mg: float
    max_thc_daily_mg: float
    initial_cbd_mg_kg_day: float
    recommended_spectrum: ProductSpectrum
    recommended_ratio: str
    recommended_route: AdministrationRoute
    recommended_concentration: float
    age_adjustment: str
    drug_interactions: List[str]
    contraindications: List[str]
    warnings: List[str]
    # REG-4 — quando True (condição grave/paliativa registrada e paciente NÃO
    # vulnerável), o clamp de THC vira AVISO (não corta): o médico é o decisor
    # (B6). Default False = clamp de THC corta como na Onda 1 (B5).
    thc_clamp_soft: bool = False


# ── Tabela de referência por condição ─────────────────────────────────────

CONDITION_PROTOCOLS: Dict[str, Dict[str, Any]] = {
    "epilepsia": {
        "ratio": "20:1", "cbd_mg_kg": 2.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "dor cronica": {
        "ratio": "1:1", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "dor neuropatica": {
        "ratio": "3:1", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "ansiedade": {
        "ratio": "CBD puro", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.BROAD_SPECTRUM,
        "concentration": 33.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "insonia": {
        "ratio": "10:1", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "fibromialgia": {
        "ratio": "3:1", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "parkinson": {
        "ratio": "10:1", "cbd_mg_kg": 1.0, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 33.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "esclerose multipla": {
        "ratio": "1:1", "cbd_mg_kg": 0.3, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "autismo": {
        "ratio": "20:1", "cbd_mg_kg": 1.0, "spectrum": ProductSpectrum.BROAD_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "tept": {
        "ratio": "5:1", "cbd_mg_kg": 0.5, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.SUBLINGUAL,
    },
    "crohn": {
        "ratio": "5:1", "cbd_mg_kg": 0.3, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 20.0, "route": AdministrationRoute.ORAL,
    },
    "nausea": {
        "ratio": "1:3", "cbd_mg_kg": 0.2, "spectrum": ProductSpectrum.FULL_SPECTRUM,
        "concentration": 10.0, "route": AdministrationRoute.SUBLINGUAL,
    },
}

# ── Interações medicamentosas CYP450 ─────────────────────────────────────

CYP450_INTERACTIONS: Dict[str, Dict[str, Any]] = {
    "varfarina": {
        "warning": "CBD inibe CYP2C9/3A4 — INR pode aumentar. Reduzir dose 50% e monitorar INR semanalmente.",
        "dose_multiplier": 0.5,
    },
    "clobazam": {
        "warning": "CBD inibe CYP2C19 — nível de norblobazam pode triplicar. Monitorar sedação.",
        "dose_multiplier": 0.75,
    },
    "valproato": {
        "warning": "Risco de hepatotoxicidade combinada. TGO/TGP obrigatório antes e quinzenalmente.",
        "dose_multiplier": 0.75,
    },
    "carbamazepina": {
        "warning": "Carbamazepina induz CYP3A4 — pode reduzir níveis de CBD. Monitorar eficácia.",
        "dose_multiplier": 1.0,
    },
    "fenitoina": {
        "warning": "CBD pode elevar níveis de fenitoína. Monitorar nível sérico.",
        "dose_multiplier": 0.75,
    },
    "fluoxetina": {
        "warning": "ISRS + CBD: potenciação serotonérgica. Iniciar 25% abaixo do padrão.",
        "dose_multiplier": 0.75,
    },
    "sertralina": {
        "warning": "ISRS + CBD: potenciação serotonérgica. Iniciar 25% abaixo do padrão.",
        "dose_multiplier": 0.75,
    },
    "omeprazol": {
        "warning": "CBD inibe CYP2C19 — pode elevar nível de omeprazol. Monitorar sintomas GI.",
        "dose_multiplier": 1.0,
    },
    "tramadol": {
        "warning": "Opioide + CBD: potenciação analgésica. Reduzir gradualmente o opioide sob supervisão.",
        "dose_multiplier": 0.75,
    },
    "morfina": {
        "warning": "Opioide + CBD: potenciação analgésica significativa. Supervisão rigorosa.",
        "dose_multiplier": 0.5,
    },
    "metformina": {
        "warning": "Interação baixa, mas monitorar glicemia na fase de ajuste.",
        "dose_multiplier": 1.0,
    },
}


def _match_condition(conditions: List[str], symptoms: List[str], complaint: str) -> str:
    """Encontra a melhor condição na tabela de protocolos."""
    all_text = " ".join(conditions + symptoms + [complaint]).lower()

    # Prioridade: condições explícitas > sintomas > queixa
    for key in CONDITION_PROTOCOLS:
        if key in all_text:
            return key

    # Fallback por sintomas comuns
    symptom_map = {
        "dor": "dor cronica",
        "insônia": "insonia",
        "insonia": "insonia",
        "ansiedade": "ansiedade",
        "epilepsia": "epilepsia",
        "convulsão": "epilepsia",
        "tremor": "parkinson",
        "náusea": "nausea",
        "nausea": "nausea",
    }
    for symptom, condition in symptom_map.items():
        if symptom in all_text:
            return condition

    return "ansiedade"  # Default conservador: CBD puro, baixa dose


def _detect_drug_interactions(medications: List[str]) -> Tuple[List[str], float]:
    """Detecta interações medicamentosas e retorna warnings + multiplicador."""
    warnings = []
    multiplier = 1.0

    for med in medications:
        med_lower = med.lower().strip()
        for drug, info in CYP450_INTERACTIONS.items():
            if drug in med_lower:
                warnings.append(info["warning"])
                multiplier = min(multiplier, info["dose_multiplier"])

    return warnings, multiplier


def _detect_contraindications(
    conditions: List[str],
    symptoms: List[str],
    medical_history: Optional[str],
) -> List[str]:
    """Detecta contraindicações absolutas."""
    contraindications = []
    all_text = " ".join(conditions + symptoms + [medical_history or ""]).lower()

    checks = {
        "esquizofrenia": "Contraindicação absoluta para THC: histórico de esquizofrenia/psicose.",
        "psicose": "Contraindicação absoluta para THC: histórico de psicose.",
        "gestante": "Contraindicação absoluta: gestação.",
        "gravida": "Contraindicação absoluta: gestação.",
        "grávida": "Contraindicação absoluta: gestação.",
        "lactante": "Contraindicação absoluta: lactação.",
        "amamentando": "Contraindicação absoluta: lactação.",
        "insuficiência hepática": "Contraindicação relativa: insuficiência hepática. Exige avaliação Child-Pugh.",
        "hepatopatia": "Contraindicação relativa: doença hepática. Monitorar função hepática.",
    }

    for term, warning in checks.items():
        if term in all_text:
            contraindications.append(warning)

    return contraindications


def calculate_safety_limits(dosage_input: DosageInput) -> SafetyLimits:
    """
    Calcula limites de segurança determinísticos.
    Esta função NUNCA chama LLM — é puramente baseada em regras farmacológicas.
    """
    age = dosage_input.age
    weight = dosage_input.weight_kg
    medications = dosage_input.current_medications or []

    # 1. Resolver condição principal
    matched_condition = _match_condition(
        dosage_input.conditions,
        dosage_input.symptoms,
        dosage_input.main_complaint,
    )
    protocol = CONDITION_PROTOCOLS[matched_condition]

    # 2. Ajuste por idade
    if age < 12:
        initial_rate = min(protocol["cbd_mg_kg"], 0.25)
        max_cbd = min(weight * 10, 600)  # Conservador pediátrico
        max_thc = 5.0  # Limite rigoroso
        age_adj = "pediátrico (<12): dose mínima, exige neuropediatra"
    elif age < 18:
        initial_rate = min(protocol["cbd_mg_kg"], 0.5)
        max_cbd = min(weight * 15, 800)
        max_thc = 10.0
        age_adj = "adolescente (12-17): dose reduzida"
    elif age > 65:
        initial_rate = min(protocol["cbd_mg_kg"], 0.5)
        max_cbd = min(weight * 15, 600)
        max_thc = 20.0
        age_adj = "geriátrico (>65): metabolismo reduzido, dose conservadora"
    else:
        initial_rate = protocol["cbd_mg_kg"]
        max_cbd = min(weight * 20, 1500)  # Protocolo Epidiolex
        max_thc = 40.0
        age_adj = "adulto: protocolo padrão"

    # 3. Ajuste por uso prévio
    if not dosage_input.prior_cannabis_use:
        initial_rate *= 0.5  # Naive: metade da dose inicial

    # 4. Interações medicamentosas
    interaction_warnings, dose_multiplier = _detect_drug_interactions(medications)
    initial_rate *= dose_multiplier
    max_cbd *= dose_multiplier

    # 5. Contraindicações
    contraindications = _detect_contraindications(
        dosage_input.conditions,
        dosage_input.symptoms,
        dosage_input.medical_history,
    )

    warnings = list(interaction_warnings)
    if dosage_input.risk_level == "alto":
        warnings.append("Risco clínico ALTO: monitoramento intensivo recomendado.")

    # 6. REG-4 — exceção de THC>0,2% (RDCs 2026). Só vale para condição grave/
    # debilitante ou paliativa registrada (REG-3) e NÃO se aplica a vulneráveis
    # (<18, gestantes, lactantes — contraindicação dura). Quando concedida, o
    # clamp de THC passa a AVISAR em vez de cortar (B6: o médico é o decisor).
    condition = dosage_input.regulatory_condition.value
    vulnerable = age < 18 or any(
        ("gesta" in c.lower() or "lacta" in c.lower()) for c in contraindications
    )
    thc_exception = condition in ("grave_debilitante", "paliativa") and not vulnerable
    if condition in ("grave_debilitante", "paliativa") and vulnerable:
        warnings.append(
            "Exceção de THC>0,2% NÃO se aplica a menores de 18, gestantes ou "
            "lactantes (contraindicação) — produto de alto teor desaconselhado."
        )

    return SafetyLimits(
        max_cbd_daily_mg=round(max_cbd, 1),
        max_thc_daily_mg=round(max_thc, 1),
        initial_cbd_mg_kg_day=round(initial_rate, 3),
        recommended_spectrum=protocol["spectrum"],
        recommended_ratio=protocol["ratio"],
        recommended_route=protocol["route"],
        recommended_concentration=protocol["concentration"],
        age_adjustment=age_adj,
        drug_interactions=interaction_warnings,
        contraindications=contraindications,
        warnings=warnings,
        thc_clamp_soft=thc_exception,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CAMADA 2 — LLM Layer (GPT-4o-mini, temperature=0)
# Gera o protocolo de titulação detalhado via function_calling.
# ═══════════════════════════════════════════════════════════════════════════════

PRESCRIBER_MODEL = "gpt-4o-mini"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(_RETRYABLE_OPENAI),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _run_prescriber_llm(system_prompt: str, user_prompt: str) -> Tuple[str, dict]:
    """
    Chama OpenAI com function_calling forçado (tool_choice="required").
    temperature=0 para determinismo máximo — zero alucinação na dosagem.
    """
    if not cb_openai.allow_request():
        raise CircuitOpenError("openai")

    try:
        response = openai_client.chat.completions.create(
            model=PRESCRIBER_MODEL,
            temperature=0,  # CRÍTICO: zero criatividade na prescrição
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=[PRESCRIBER_TOOL_DEFINITION],
            tool_choice={"type": "function", "function": {"name": "recommend_dosage"}},
        )

        tool_call = response.choices[0].message.tool_calls[0]
        raw_args = tool_call.function.arguments
        usage = response.usage

        cb_openai.record_success()

        return raw_args, {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        }

    except CircuitOpenError:
        raise
    except Exception as exc:
        cb_openai.record_failure()
        logger.warning("Prescriber LLM falhou (retry automático): %s", str(exc))
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# SAFETY CLAMP — Garante que o LLM respeita os limites do Rules Engine
# ═══════════════════════════════════════════════════════════════════════════════

def _thc_fraction_from_ratio(ratio: str) -> float:
    """
    Fração de THC no total canabinoide a partir do ratio CBD:THC (CLI-2 / 29.2 R2).
    Ex.: '20:1' -> 1/21 ≈ 0.048; '1:1' -> 0.5; '1:3' -> 0.75; 'CBD puro' -> 0.0.
    Retorna 0.0 quando não há THC ou o ratio é ininteligível (clamp THC inativo).
    """
    if not ratio:
        return 0.0
    r = ratio.strip().lower()
    if "puro" in r or "pure" in r or "isolado" in r or "cbd only" in r:
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)", r)
    if not m:
        return 0.0
    cbd_parts = float(m.group(1))
    thc_parts = float(m.group(2))
    total = cbd_parts + thc_parts
    return (thc_parts / total) if total > 0 else 0.0


# REG-4 — teor de THC do PRODUTO (RDCs 2026). Acima de 0,2% (m/v ≈ 2 mg/mL) o
# produto só é indicado para condição grave/debilitante ou que ameace a vida
# (paliativa). 0,3% é o teto de cultivo/matéria-prima; usamos a régua mais
# conservadora (0,2%) para sinalizar mais cedo. Sempre prontidão, nunca aprovação.
THC_PRODUCT_THRESHOLD_MG_ML = 2.0  # ≈ 0,2% m/v


def thc_mg_per_ml(ratio: str, concentration_mg_ml: float) -> float:
    """THC em mg/mL do produto, derivado do ratio CBD:THC e da concentração total."""
    return float(concentration_mg_ml or 0) * _thc_fraction_from_ratio(ratio)


def is_high_thc_product(ratio: str, concentration_mg_ml: float) -> bool:
    """True se o produto excede 0,2% de THC (≈ 2 mg/mL) — gatilho de exceção REG-4."""
    return thc_mg_per_ml(ratio, concentration_mg_ml) > THC_PRODUCT_THRESHOLD_MG_ML


def _clamp_recommendation(
    recommendation: DosageRecommendation,
    limits: SafetyLimits,
) -> DosageRecommendation:
    """
    Força os limites de segurança sobre a saída do LLM.
    O Rules Engine SEMPRE prevalece — clampa CBD (max_cbd_daily_mg) E THC
    (max_thc_daily_mg, derivado do ratio — CLI-2 / 29.2 R2).
    """
    thc_fraction = _thc_fraction_from_ratio(recommendation.cannabinoid_ratio)

    clamped_protocol = []
    for step in recommendation.titration_protocol:
        clamped_mg = min(step.total_daily_mg, limits.max_cbd_daily_mg)
        if step.total_daily_mg > limits.max_cbd_daily_mg:
            logger.warning(
                "Safety clamp CBD: dose cortada de %.1f mg para %.1f mg (limite Rules Engine)",
                step.total_daily_mg, clamped_mg,
            )

        # Clamp de THC: deriva o THC do total pelo ratio e corta contra max_thc.
        # Espelha o clamp de CBD; relevante para ratios ricos em THC (ex.: '1:3').
        if thc_fraction > 0:
            thc_mg = clamped_mg * thc_fraction
            if thc_mg > limits.max_thc_daily_mg:
                if limits.thc_clamp_soft:
                    # REG-4: condição grave/paliativa registrada (paciente não
                    # vulnerável) — exceção legal p/ THC>0,2%. A IA AVISA, não corta;
                    # o médico é o decisor (B6).
                    logger.warning(
                        "Safety clamp THC (informativo / condição grave): THC %.1f mg "
                        "> %.1f mg/dia mantido para decisão médica (exceção RDCs 2026)",
                        thc_mg, limits.max_thc_daily_mg,
                    )
                else:
                    thc_capped_total = limits.max_thc_daily_mg / thc_fraction
                    logger.warning(
                        "Safety clamp THC: dose cortada de %.1f mg para %.1f mg "
                        "(THC %.1f mg > limite %.1f mg/dia)",
                        clamped_mg, thc_capped_total, thc_mg, limits.max_thc_daily_mg,
                    )
                    clamped_mg = min(clamped_mg, thc_capped_total)

        # Recalcula gotas se a dose foi cortada por qualquer limite (CBD ou THC).
        # Limita ao intervalo do schema (1..30) — a dose em mg é a fonte de
        # verdade; gotas é derivada e nunca deve invalidar o TitrationStep.
        if clamped_mg < step.total_daily_mg:
            mg_per_drop = step.concentration_mg_ml * DROP_VOLUME_ML
            total_drops = clamped_mg / mg_per_drop if mg_per_drop > 0 else step.drops_per_dose
            drops_per_dose = max(1, min(30, int(total_drops / step.doses_per_day)))
        else:
            drops_per_dose = step.drops_per_dose

        clamped_protocol.append(TitrationStep(
            phase=step.phase,
            day_range=step.day_range,
            drops_per_dose=drops_per_dose,
            doses_per_day=step.doses_per_day,
            concentration_mg_ml=step.concentration_mg_ml,
            total_daily_mg=round(clamped_mg, 1),
            observations=step.observations,
        ))

    # Merge contraindicações e interações do Rules Engine
    all_contraindications = list(set(
        recommendation.contraindications + limits.contraindications
    ))
    all_interactions = list(set(
        recommendation.drug_interactions + limits.drug_interactions
    ))

    # Ajustar confidence_score se houver contraindicações
    confidence = recommendation.confidence_score
    if limits.contraindications:
        confidence = min(confidence, 0.5)
    if limits.drug_interactions:
        confidence = min(confidence, 0.6)

    # Teto diário final: menor entre o sugerido, o limite de CBD e o limite de
    # THC convertido para total canabinoide pelo ratio (CLI-2).
    max_daily = min(recommendation.max_daily_mg, limits.max_cbd_daily_mg)
    if thc_fraction > 0 and not limits.thc_clamp_soft:
        max_daily = min(max_daily, limits.max_thc_daily_mg / thc_fraction)

    return DosageRecommendation(
        cannabinoid_ratio=recommendation.cannabinoid_ratio,
        spectrum=recommendation.spectrum,
        administration_route=recommendation.administration_route,
        concentration_mg_ml=recommendation.concentration_mg_ml,
        titration_protocol=clamped_protocol,
        max_daily_mg=round(max_daily, 1),
        clinical_rationale=recommendation.clinical_rationale,
        contraindications=all_contraindications,
        drug_interactions=all_interactions,
        monitoring_checkpoints=recommendation.monitoring_checkpoints,
        confidence_score=round(confidence, 2),
        evidence_sources=recommendation.evidence_sources,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR — Rules Engine → LLM → Safety Clamp
# ═══════════════════════════════════════════════════════════════════════════════

def run_prescriber(dosage_input: DosageInput) -> Tuple[DosageRecommendation, SafetyLimits, dict]:
    """
    Executa o pipeline completo do Prescriber:
      1. Rules Engine calcula limites de segurança
      2. LLM gera protocolo de titulação detalhado
      3. Safety Clamp garante que LLM respeita os limites

    Returns:
        Tuple[DosageRecommendation, SafetyLimits, dict]:
            - Recomendação validada e clampada
            - Limites de segurança calculados
            - Métricas de tokens do LLM
    """
    start = time.time()

    # ── Camada 1: Rules Engine ────────────────────────────────────────────
    limits = calculate_safety_limits(dosage_input)
    logger.info(
        "Rules Engine: max_cbd=%.1f mg/dia, max_thc=%.1f mg/dia, ratio=%s, "
        "interactions=%d, contraindications=%d",
        limits.max_cbd_daily_mg, limits.max_thc_daily_mg,
        limits.recommended_ratio,
        len(limits.drug_interactions), len(limits.contraindications),
    )

    # ── Camada 2: LLM (temperature=0) ────────────────────────────────────
    system_prompt = get_prompt("prescriber_system").text.format(
        patient_name=dosage_input.patient_name,
        age=dosage_input.age,
        weight_kg=dosage_input.weight_kg,
        height_cm=dosage_input.height_cm or "N/I",
        main_complaint=dosage_input.main_complaint,
        symptoms=", ".join(dosage_input.symptoms),
        conditions=", ".join(dosage_input.conditions) if dosage_input.conditions else "Nenhuma confirmada",
        current_medications=", ".join(dosage_input.current_medications or []) or "Nenhuma",
        allergies=", ".join(dosage_input.allergies or []) or "Nenhuma",
        medical_history=dosage_input.medical_history or "Não informado",
        prior_cannabis_use="Sim" if dosage_input.prior_cannabis_use else "Não (naive)",
        risk_level=dosage_input.risk_level,
    )

    raw_output, tokens = _run_prescriber_llm(system_prompt, get_prompt("prescriber_user").text)

    # ── Parse e validação Pydantic ────────────────────────────────────────
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Prescriber LLM retornou JSON inválido:\n{raw_output}")

    try:
        recommendation = DosageRecommendation(**parsed)
    except ValidationError as e:
        raise ValueError(f"Prescriber output não corresponde ao schema:\n{e}")

    # ── Camada 3: Safety Clamp ────────────────────────────────────────────
    clamped = _clamp_recommendation(recommendation, limits)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(
        "Prescriber concluído em %d ms: ratio=%s, spectrum=%s, max_daily=%.1f mg, "
        "confidence=%.2f, phases=%d",
        elapsed_ms,
        clamped.cannabinoid_ratio,
        clamped.spectrum.value,
        clamped.max_daily_mg,
        clamped.confidence_score,
        len(clamped.titration_protocol),
    )

    return clamped, limits, tokens
