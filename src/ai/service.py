from __future__ import annotations

import logging
import time
import hashlib
from typing import Any, Dict, Optional

from flask import g
from pydantic import ValidationError

from src.ai.clinical_flow import build_clinical_flow
from src.ai.schemas import AnamnesisInput
from src.ai.guardrails import apply_to_output_dict, validate_input
from src.repositories.ai_audit_repository import save_ai_audit_log
from src.repositories.patient_repository import get_or_create_patient_by_name
from src.ai.pricing import calculate_cost
from src.services.billing_service import (
    check_ai_allowance,
    record_ai_usage,
    BillingLimitExceeded,
)


# Sprint 2 Track Reg: prompt_version + prompt_hash REAIS substituem o
# placeholder eterno (prompt_version="v1.0" + sha256("v1.0")). Helpers
# abaixo derivam strings agregadas a partir do dict prompts_used que
# clinical_flow.run() agora popula.

_NA = "n/a"


def _aggregate_prompt_version(prompts_used: Dict[str, Dict[str, Any]]) -> str:
    """
    Concat ordenado de "<stage>:<version>" pra prompt_version.
    Ex: "anamnese:v1.0.0+cientifico:hardcoded+prescritor:v1.0.0+tratamento:v1.0.0".
    Se vazio, retorna "n/a" (pre-flow paths).
    """
    if not prompts_used:
        return _NA
    parts = sorted(
        f"{stage}:{(meta or {}).get('version', _NA)}"
        for stage, meta in prompts_used.items()
        if meta
    )
    return "+".join(parts) if parts else _NA


def _aggregate_prompt_hash(prompts_used: Dict[str, Dict[str, Any]]) -> str:
    """
    SHA-256 da concat ordenada dos hashes individuais. Deterministico:
    mesma combinacao de prompts -> mesmo hash agregado.
    Se vazio, retorna "n/a" (pre-flow paths).
    """
    if not prompts_used:
        return _NA
    hashes = sorted(
        (meta or {}).get("hash", "")
        for stage, meta in prompts_used.items()
        if meta
    )
    if not any(hashes):
        return _NA
    concat = "|".join(hashes)
    return hashlib.sha256(concat.encode("utf-8")).hexdigest()


logger = logging.getLogger("cannabia.ai")


def run_governed_flow(
    data: Dict[str, Any],
    *,
    clinic_id: Optional[int],
    endpoint: str,
    user_id: Optional[str] = None,
    request_id: Optional[str] = None,
    flow: Any = None,
    anamnesis: Optional[AnamnesisInput] = None,
    patient_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Caminho de IA governado ÚNICO (IA-2 / 29.4 R1): billing (check_ai_allowance/
    record_ai_usage) + guardrails (validate_input + Camada 4) + validação +
    auditoria (save_ai_audit_log) em volta de `flow.run()`, para TODOS os canais
    do paciente (/ai/test, WhatsApp, Triagem).

    NÃO altera o modelo síncrono — o cutover assíncrono é Onda 2; aqui só
    governa a execução atual. `anamnesis` pré-construído pode ser passado
    (Triagem/WhatsApp já montam o AnamnesisInput); senão é validado de `data`.
    `data` é o payload bruto usado por guardrails/auditoria.
    """
    start_total = time.time()

    if clinic_id is None:
        raise RuntimeError("clinic_id não encontrado no contexto da request")

    model_name = "gpt-4o-mini"
    # Pre-flow paths (billing/security/validation/error) gravam "n/a"
    # honestamente. So apos flow.run() temos o snapshot real dos prompts.
    pre_flow_prompt_version = _NA
    pre_flow_prompt_hash = _NA

    resolved_name = patient_name or data.get("patient_name")
    if not resolved_name:
        raise ValueError("patient_name é obrigatório.")

    patient_id = get_or_create_patient_by_name(clinic_id, resolved_name)
    flow = flow or build_clinical_flow()

    # Billing — verificação de limites (Fase 5.3)
    allowance = check_ai_allowance(clinic_id)
    if not allowance.allowed:
        save_ai_audit_log(
            clinic_id=clinic_id,
            patient_id=patient_id,
            request_id=request_id,
            endpoint=endpoint,
            user_id=user_id,
            input_payload=data,
            output_payload=None,
            status="billing_blocked",
            error_message=allowance.message,
            model=model_name,
            prompt_version=pre_flow_prompt_version,
            prompt_hash=pre_flow_prompt_hash,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            clinical_time_ms=None,
            treatment_time_ms=None,
            report_time_ms=None,
            total_time_ms=None,
            estimated_cost_usd=None,
        )
        raise BillingLimitExceeded(
            clinic_id=clinic_id,
            resource="ai_requests",
            current=allowance.requests_used,
            limit=allowance.requests_limit,
        )

    # Segurança — guardrails multi-camada (Fase 3.1)
    guardrail_result = validate_input(data)
    if not guardrail_result.passed:
        security_error = ValueError(
            f"Guardrail bloqueou input [{guardrail_result.blocked_by.value}]: "
            f"{guardrail_result.reason}"
        )
        save_ai_audit_log(
            clinic_id=clinic_id,
            patient_id=patient_id,
            request_id=request_id,
            endpoint=endpoint,
            user_id=user_id,
            input_payload=data,
            output_payload=None,
            status="security_blocked",
            error_message=str(security_error),
            model=model_name,
            prompt_version=pre_flow_prompt_version,
            prompt_hash=pre_flow_prompt_hash,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            clinical_time_ms=None,
            treatment_time_ms=None,
            report_time_ms=None,
            total_time_ms=None,
            estimated_cost_usd=None,
        )
        raise ValueError("Possível tentativa de prompt injection detectada.")

    # Validação estrutural (se o caller não montou o AnamnesisInput)
    if anamnesis is None:
        try:
            anamnesis = AnamnesisInput(**data)
        except ValidationError as validation_error:
            save_ai_audit_log(
                clinic_id=clinic_id,
                patient_id=patient_id,
                request_id=request_id,
                endpoint=endpoint,
                user_id=user_id,
                input_payload=data,
                output_payload=None,
                status="validation_error",
                error_message=str(validation_error),
                model=model_name,
                prompt_version=pre_flow_prompt_version,
                prompt_hash=pre_flow_prompt_hash,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                clinical_time_ms=None,
                treatment_time_ms=None,
                report_time_ms=None,
                total_time_ms=None,
                estimated_cost_usd=None,
            )
            raise ValueError("Dados inválidos.")

    try:
        result = flow.run(anamnesis)

        total_time_ms = int((time.time() - start_total) * 1000)

        # Sprint 2 Track Reg: extrai snapshot dos prompts efetivamente
        # usados pelo flow. clinical_flow.run() popula prompts_used
        # com 4 metas (anamnese/tratamento/prescritor/cientifico).
        prompts_used = result.get("prompts_used", {}) or {}
        effective_prompt_version = _aggregate_prompt_version(prompts_used)
        effective_prompt_hash = _aggregate_prompt_hash(prompts_used)

        token_usage = result.get("token_usage", {})
        input_tokens = token_usage.get("input")
        output_tokens = token_usage.get("output")
        total_tokens = token_usage.get("total")

        # Cost honesto: cada stage pode usar modelo diferente (ex.: report
        # usa gemini-2.5-flash quando RAG ativo). Soma calculate_cost por
        # stage com seu proprio modelo. Fallback para o calculo agregado
        # antigo caso tokens_per_stage nao venha (compat).
        tokens_per_stage = result.get("tokens_per_stage") or {}
        if tokens_per_stage:
            estimated_cost = round(
                sum(
                    calculate_cost(
                        info.get("model", model_name),
                        (info.get("tokens") or {}).get("input", 0),
                        (info.get("tokens") or {}).get("output", 0),
                    )
                    for info in tokens_per_stage.values()
                ),
                6,
            )
            # ai_audit_logs.model VARCHAR(50): concat ordenado deduplicado
            # dos modelos efetivamente usados. Ex.: "gpt-4o-mini+gemini-2.5-flash".
            effective_model = "+".join(
                sorted({info.get("model", model_name) for info in tokens_per_stage.values()})
            )
        else:
            estimated_cost = calculate_cost(
                model_name,
                input_tokens,
                output_tokens,
            )
            effective_model = model_name

        # Billing — registra consumo após execução bem-sucedida (Fase 5.3)
        record_ai_usage(
            clinic_id=clinic_id,
            tokens_used=total_tokens or 0,
            estimated_cost_usd=estimated_cost,
        )

        prescription_tokens = (
            (result.get("tokens_per_stage") or {}).get("prescription", {}).get("tokens")
            or {}
        )
        save_ai_audit_log(
            clinic_id=clinic_id,
            patient_id=patient_id,
            request_id=request_id,
            endpoint=endpoint,
            user_id=user_id,
            input_payload=data,
            output_payload=result,
            status="success",
            error_message=None,
            model=effective_model,
            prompt_version=effective_prompt_version,
            prompt_hash=effective_prompt_hash,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            clinical_time_ms=result.get("timings_ms", {}).get("clinical"),
            treatment_time_ms=result.get("timings_ms", {}).get("treatment"),
            report_time_ms=result.get("timings_ms", {}).get("report"),
            total_time_ms=total_time_ms,
            estimated_cost_usd=estimated_cost,
            prescription_time_ms=result.get("timings_ms", {}).get("prescription"),
            prescription_input_tokens=prescription_tokens.get("input"),
            prescription_output_tokens=prescription_tokens.get("output"),
        )

        # Camada 4 (Sprint 1 Track B.1): sanitiza output do LLM antes de
        # devolver ao paciente/frontend. Audit log acima ja gravou o
        # `result` cru pra rastreabilidade. Aqui aplica regex de output
        # (script tag, env var name, secret patterns) recursivamente nos
        # string-leaves do dict; se algum padrao foi detectado, sinaliza
        # via flag externa requires_review=True (sem bloquear — calibra
        # progressiva, Sprint 4 endurece).
        sanitized_result, output_guardrail = apply_to_output_dict(result)
        sanitized_result["_guardrail_output"] = {
            "passed": output_guardrail.passed,
            "reason": output_guardrail.reason,
            "requires_review": not output_guardrail.passed,
        }
        if not output_guardrail.passed:
            logger.warning(
                "Output sanitizado pela Camada 4 (request_id=%s, reason=%s)",
                request_id,
                output_guardrail.reason,
            )
        return sanitized_result

    except Exception as execution_error:

        total_time_ms = int((time.time() - start_total) * 1000)

        save_ai_audit_log(
            clinic_id=clinic_id,
            patient_id=patient_id,
            request_id=request_id,
            endpoint=endpoint,
            user_id=user_id,
            input_payload=data,
            output_payload=None,
            status="error",
            error_message=str(execution_error),
            model=model_name,
            prompt_version=pre_flow_prompt_version,
            prompt_hash=pre_flow_prompt_hash,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            clinical_time_ms=None,
            treatment_time_ms=None,
            report_time_ms=None,
            total_time_ms=total_time_ms,
            estimated_cost_usd=None,
        )

        logger.exception(
            "Erro interno no pipeline clínico",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "clinic_id": clinic_id,
                "patient_id": patient_id,
            },
        )
        raise RuntimeError("Erro interno no processamento clínico.")


class CannabIAService:

    def __init__(self, execution_mode: Optional[str] = None) -> None:
        self.execution_mode = execution_mode
        self.flow = build_clinical_flow(mode=execution_mode)

    def process_patient_case(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Delega ao caminho governado único (IA-2). Mantém o contrato do /ai/test:
        # clinic_id/user_id/request_id resolvidos do contexto Flask.
        return run_governed_flow(
            data,
            clinic_id=getattr(g, "clinic_id", None),
            endpoint="/ai/test",
            user_id=getattr(g, "user_id", None),
            request_id=getattr(g, "request_id", None),
            flow=self.flow,
        )
