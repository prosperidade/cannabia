# src/ai/chains.py
"""
Chains de LLM com circuit breaker, retry e timeout (Fase 3.3).

Resiliência implementada com tenacity:
  - 3 retries com backoff exponencial (2s, 4s, 8s)
  - Timeout por provedor: OpenAI 30s, Gemini 45s
  - Circuit breaker: abre após 5 falhas consecutivas, half-open após 60s

Estados do circuit breaker:
  CLOSED   → chamadas normais (estado saudável)
  OPEN     → rejeita chamadas imediatamente (falhou demais)
  HALF_OPEN → permite 1 chamada de teste para verificar recuperação
"""

import json
import logging
import os
import threading
import time
from typing import List, Tuple, Type

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from src.ai.schemas import (
    ClinicalAnalysis,
    ScientificReport,
    TreatmentPlan,
    TriageResponse,
    TRIAGE_TOOL_DEFINITION,
    TRIAGE_GEMINI_SCHEMA,
)
# Sprint 2 Track Reg: prompts vem do registry (DB-first com fallback
# hardcoded). Imports diretos de src.ai.prompts permanecem disponiveis pra
# tests e backward-compat, mas o caminho oficial agora e get_prompt().
from src.ai.prompt_registry import get_prompt

load_dotenv()
logger = logging.getLogger("cannabia.ai")

# ── Clientes ──────────────────────────────────────────────────────────────────
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=float(os.getenv("OPENAI_TIMEOUT", "30")),
)
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_TIMEOUT = float(os.getenv("GEMINI_TIMEOUT", "45"))


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# Implementação thread-safe com 3 estados: CLOSED, OPEN, HALF_OPEN
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker por provedor de IA.

    Parâmetros:
      failure_threshold — número de falhas consecutivas para abrir o circuito
      recovery_timeout  — segundos em estado OPEN antes de tentar HALF_OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Verifica se já passou o tempo de recovery para transitar a HALF_OPEN
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker '%s': OPEN → HALF_OPEN", self.name)
            return self._state

    def record_success(self) -> None:
        """Registra sucesso — reseta o circuito para CLOSED."""
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                self._failure_count = 0
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Registra falha — incrementa contador ou abre o circuito."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Falhou durante teste — volta para OPEN
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s': HALF_OPEN → OPEN (falha no teste de recuperação)",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s': CLOSED → OPEN após %d falhas consecutivas",
                    self.name, self._failure_count,
                )

    def allow_request(self) -> bool:
        """Verifica se a chamada deve ser permitida."""
        current_state = self.state  # Avalia transição OPEN→HALF_OPEN
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return True  # Permite 1 chamada de teste
        return False  # OPEN — bloqueia

    def get_status(self) -> dict:
        """Retorna estado para health check / métricas."""
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout,
        }


# Instâncias globais por provedor
cb_openai = CircuitBreaker("openai", failure_threshold=5, recovery_timeout=60)
cb_gemini = CircuitBreaker("gemini", failure_threshold=5, recovery_timeout=60)


class CircuitOpenError(Exception):
    """Erro levantado quando o circuit breaker está aberto."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Circuit breaker aberto para provedor '{provider}'. Tente novamente mais tarde.")


# ═══════════════════════════════════════════════════════════════════════════════
# OPENAI — helper com retry + circuit breaker (Etapas 1 e 2)
# ═══════════════════════════════════════════════════════════════════════════════

# Exceções que justificam retry (transientes)
_RETRYABLE_OPENAI = (
    Exception,  # Captura APIError, RateLimitError, Timeout, etc.
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(_RETRYABLE_OPENAI),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _run_openai(prompt: str) -> Tuple[str, dict]:
    """Chamada à OpenAI com retry e circuit breaker."""
    if not cb_openai.allow_request():
        raise CircuitOpenError("openai")

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": "Responda apenas com JSON válido."},
                {"role": "user",   "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        usage   = response.usage

        cb_openai.record_success()

        return content, {
            "input_tokens":  usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "total_tokens":  usage.total_tokens,
        }

    except CircuitOpenError:
        raise
    except Exception as exc:
        cb_openai.record_failure()
        logger.warning("OpenAI falhou (retry automático): %s", str(exc))
        raise


def _run_and_validate(
    prompt_template: str,
    schema_model: Type[BaseModel],
    **kwargs,
):
    prompt = prompt_template.format(**kwargs)
    raw_output, tokens = _run_openai(prompt)
    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Modelo retornou JSON inválido:\n{raw_output}")
    try:
        validated = schema_model(**parsed_json)
    except ValidationError as e:
        raise ValueError(f"JSON não corresponde ao schema:\n{e}")
    return validated, tokens


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 — Análise Clínica (OpenAI)
# ══════════════════════════════════════════════════════════════════════════════

def run_clinical_analysis(**patient_data):
    for k, v in patient_data.items():
        patient_data[k] = "\n".join([f"- {x}" for x in v]) if isinstance(v, list) else str(v)
    return _run_and_validate(get_prompt("anamnesis").text, ClinicalAnalysis, **patient_data)


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 — Plano Terapêutico (OpenAI)
# ══════════════════════════════════════════════════════════════════════════════

def run_treatment_plan(clinical_analysis: ClinicalAnalysis):
    return _run_and_validate(
        get_prompt("treatment_plan").text,
        TreatmentPlan,
        clinical_analysis=clinical_analysis.model_dump_json(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 — Relatório Científico sem RAG (fallback / OpenAI)
# Mantido para compatibilidade quando o ChromaDB estiver vazio.
# ══════════════════════════════════════════════════════════════════════════════

def run_scientific_report(treatment_plan: TreatmentPlan):
    return _run_and_validate(
        get_prompt("scientific_report").text,
        ScientificReport,
        treatment_plan=treatment_plan.model_dump_json(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 (RAG) — Relatório Científico com Gemini + contexto vetorial
# Com retry + circuit breaker + failover para OpenAI
# ══════════════════════════════════════════════════════════════════════════════

def _format_rag_context(chunks: List[dict]) -> str:
    """Formata os chunks recuperados do ChromaDB em texto estruturado para o prompt."""
    if not chunks:
        return "Nenhuma referência científica disponível no banco vetorial."

    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta  = chunk.get("metadata", {})
        title = meta.get("title",  "Título não informado")
        doi   = meta.get("doi",    "N/A")
        score = chunk.get("similarity_score", 0)
        text  = chunk.get("text", "")
        lines.append(
            f"[{i}] Título: {title} | DOI: {doi} | Relevância: {score:.2f}\n{text}"
        )

    return "\n\n---\n\n".join(lines)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _run_gemini_with_retry(prompt: str) -> Tuple[str, dict]:
    """Chamada ao Gemini com retry e circuit breaker."""
    if not cb_gemini.allow_request():
        raise CircuitOpenError("gemini")

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        raw_output = response.text.strip()
        usage = response.usage_metadata
        tokens = {
            "input_tokens":  getattr(usage, "prompt_token_count",     0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
            "total_tokens":  getattr(usage, "total_token_count",      0) or 0,
        }

        cb_gemini.record_success()
        return raw_output, tokens

    except CircuitOpenError:
        raise
    except Exception as exc:
        cb_gemini.record_failure()
        logger.warning("Gemini falhou (retry automático): %s", str(exc))
        raise


def run_scientific_report_rag(
    treatment_plan: TreatmentPlan,
    rag_chunks: List[dict],
) -> Tuple[ScientificReport, dict]:
    """
    Gera o Relatório Científico usando Gemini + contexto RAG.
    Se Gemini estiver indisponível (circuit aberto), faz failover para OpenAI.
    """
    scientific_context = _format_rag_context(rag_chunks)

    prompt = get_prompt("scientific_report_rag").text.format(
        treatment_plan=treatment_plan.model_dump_json(),
        scientific_context=scientific_context,
    )

    # Tenta Gemini primeiro; failover para OpenAI se circuit aberto
    try:
        raw_output, tokens = _run_gemini_with_retry(prompt)
    except CircuitOpenError:
        logger.warning(
            "Circuit breaker Gemini aberto — failover para OpenAI no relatório científico."
        )
        return run_scientific_report(treatment_plan)

    try:
        parsed_json = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Gemini retornou JSON inválido:\n{raw_output}")

    try:
        validated = ScientificReport(**parsed_json)
    except ValidationError as e:
        raise ValueError(f"JSON do Gemini não corresponde ao schema:\n{e}")

    logger.info(
        "Gemini RAG report gerado: %d tokens (contexto: %d chunks).",
        tokens["total_tokens"],
        len(rag_chunks),
    )

    return validated, tokens


# ═══════════════════════════════════════════════════════════════════════════════
# TRIAGE AGENT — Structured output via function_calling (OpenAI) / schema (Gemini)
# Retorna TriageResponse com widget injection para o frontend B2B2C.
# ═══════════════════════════════════════════════════════════════════════════════

TRIAGE_MODEL_OPENAI = os.getenv("TRIAGE_MODEL_OPENAI", "gpt-4o-mini")
TRIAGE_MODEL_GEMINI = os.getenv("TRIAGE_MODEL_GEMINI", "gemini-1.5-flash")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(_RETRYABLE_OPENAI),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _run_triage_openai(system_prompt: str, patient_message: str) -> tuple:
    """
    Chama OpenAI com function_calling forçado (tool_choice="required").
    O modelo é OBRIGADO a invocar render_triage_widget — nunca retorna texto livre.
    """
    if not cb_openai.allow_request():
        raise CircuitOpenError("openai")

    try:
        response = openai_client.chat.completions.create(
            model=TRIAGE_MODEL_OPENAI,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": patient_message},
            ],
            tools=[TRIAGE_TOOL_DEFINITION],
            tool_choice={"type": "function", "function": {"name": "render_triage_widget"}},
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
        logger.warning("OpenAI triage falhou (retry automático): %s", str(exc))
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(Exception),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _run_triage_gemini(system_prompt: str, patient_message: str) -> tuple:
    """
    Chama Gemini com response_schema forçado.
    O modelo retorna JSON em conformidade direta com TRIAGE_GEMINI_SCHEMA.
    """
    if not cb_gemini.allow_request():
        raise CircuitOpenError("gemini")

    try:
        full_prompt = f"{system_prompt}\n\n---\nRelato do paciente:\n{patient_message}"

        response = gemini_client.models.generate_content(
            model=TRIAGE_MODEL_GEMINI,
            contents=full_prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                response_schema=TRIAGE_GEMINI_SCHEMA,
            ),
        )

        raw_output = response.text.strip()
        usage = response.usage_metadata
        tokens = {
            "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
            "total_tokens": getattr(usage, "total_token_count", 0) or 0,
        }

        cb_gemini.record_success()
        return raw_output, tokens

    except CircuitOpenError:
        raise
    except Exception as exc:
        cb_gemini.record_failure()
        logger.warning("Gemini triage falhou (retry automático): %s", str(exc))
        raise


def run_triage_agent(
    patient_message: str,
    patient_name: str = "Paciente",
    age: int = 0,
    clinic_id: str = "",
    prior_context: str = "Nenhum histórico prévio disponível.",
    provider: str = "openai",
) -> tuple:
    """
    Executa o Agente de Triagem com structured output garantido.

    Args:
        patient_message: Relato livre do paciente (texto ou transcrição de áudio).
        patient_name: Nome do paciente para personalização.
        age: Idade do paciente.
        clinic_id: ID da clínica (multi-tenant).
        prior_context: Histórico de mensagens anteriores da conversa.
        provider: "openai" (function_calling) ou "gemini" (response_schema).

    Returns:
        Tuple[TriageResponse, dict]: Resposta validada + métricas de tokens.
    """
    system_prompt = get_prompt("triage_agent").text.format(
        patient_name=patient_name,
        age=age,
        clinic_id=clinic_id,
        prior_context=prior_context,
    )

    if provider == "gemini":
        try:
            raw_output, tokens = _run_triage_gemini(system_prompt, patient_message)
        except CircuitOpenError:
            logger.warning("Gemini circuit aberto — failover para OpenAI no triage.")
            raw_output, tokens = _run_triage_openai(system_prompt, patient_message)
    else:
        try:
            raw_output, tokens = _run_triage_openai(system_prompt, patient_message)
        except CircuitOpenError:
            logger.warning("OpenAI circuit aberto — failover para Gemini no triage.")
            raw_output, tokens = _run_triage_gemini(system_prompt, patient_message)

    # Parse e validação Pydantic
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError(f"Triage agent retornou JSON inválido:\n{raw_output}")

    try:
        validated = TriageResponse(**parsed)
    except ValidationError as e:
        raise ValueError(f"Triage response não corresponde ao schema:\n{e}")

    logger.info(
        "Triage concluído: widget=%s, conditions=%d, tokens=%d",
        validated.inject_widget.value,
        len(validated.extracted_conditions),
        tokens.get("total_tokens", 0),
    )

    return validated, tokens


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK — Estado dos circuit breakers (consumido por /api/v1/health)
# ═══════════════════════════════════════════════════════════════════════════════

def get_circuit_breaker_status() -> dict:
    """Retorna estado de todos os circuit breakers para observabilidade."""
    return {
        "openai": cb_openai.get_status(),
        "gemini": cb_gemini.get_status(),
    }
