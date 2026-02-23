from __future__ import annotations

import logging
import time
import hashlib
from typing import Any, Dict, Optional

from flask import g
from pydantic import ValidationError

from src.ai.pipeline import CannabIAPipeline
from src.ai.schemas import AnamnesisInput
from src.ai.validators import validate_anamnesis_security
from src.repositories.ai_audit_repository import save_ai_audit_log
from src.repositories.patient_repository import get_or_create_patient_by_name
from src.ai.pricing import calculate_cost


logger = logging.getLogger("cannabia.ai")


class CannabIAService:

    def __init__(self) -> None:
        self.pipeline = CannabIAPipeline()

    def process_patient_case(self, data: Dict[str, Any]) -> Dict[str, Any]:

        start_total = time.time()

        request_id: Optional[str] = getattr(g, "request_id", None)
        user_id: Optional[str] = getattr(g, "user_id", None)
        clinic_id: Optional[int] = getattr(g, "clinic_id", None)

        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto da request")

        model_name = "gpt-4o-mini"
        prompt_version = "v1.0"
        prompt_hash = hashlib.sha256(prompt_version.encode()).hexdigest()

        patient_name = data.get("patient_name")
        if not patient_name:
            raise ValueError("patient_name é obrigatório.")

        patient_id = get_or_create_patient_by_name(clinic_id, patient_name)

        # Segurança
        try:
            validate_anamnesis_security(data)
        except ValueError as security_error:
            save_ai_audit_log(
                clinic_id=clinic_id,
                patient_id=patient_id,
                request_id=request_id,
                endpoint="/ai/test",
                user_id=user_id,
                input_payload=data,
                output_payload=None,
                status="security_blocked",
                error_message=str(security_error),
                model=model_name,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
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

        # Validação estrutural
        try:
            anamnesis = AnamnesisInput(**data)
        except ValidationError as validation_error:
            save_ai_audit_log(
                clinic_id=clinic_id,
                patient_id=patient_id,
                request_id=request_id,
                endpoint="/ai/test",
                user_id=user_id,
                input_payload=data,
                output_payload=None,
                status="validation_error",
                error_message=str(validation_error),
                model=model_name,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
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
            result = self.pipeline.run(anamnesis)

            total_time_ms = int((time.time() - start_total) * 1000)

            token_usage = result.get("token_usage", {})
            input_tokens = token_usage.get("input")
            output_tokens = token_usage.get("output")
            total_tokens = token_usage.get("total")

            estimated_cost = calculate_cost(
                model_name,
                input_tokens,
                output_tokens,
            )

            save_ai_audit_log(
                clinic_id=clinic_id,
                patient_id=patient_id,
                request_id=request_id,
                endpoint="/ai/test",
                user_id=user_id,
                input_payload=data,
                output_payload=result,
                status="success",
                error_message=None,
                model=model_name,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                clinical_time_ms=result.get("timings_ms", {}).get("clinical"),
                treatment_time_ms=result.get("timings_ms", {}).get("treatment"),
                report_time_ms=result.get("timings_ms", {}).get("report"),
                total_time_ms=total_time_ms,
                estimated_cost_usd=estimated_cost,
            )

            return result

        except Exception as execution_error:

            total_time_ms = int((time.time() - start_total) * 1000)

            save_ai_audit_log(
                clinic_id=clinic_id,
                patient_id=patient_id,
                request_id=request_id,
                endpoint="/ai/test",
                user_id=user_id,
                input_payload=data,
                output_payload=None,
                status="error",
                error_message=str(execution_error),
                model=model_name,
                prompt_version=prompt_version,
                prompt_hash=prompt_hash,
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                clinical_time_ms=None,
                treatment_time_ms=None,
                report_time_ms=None,
                total_time_ms=total_time_ms,
                estimated_cost_usd=None,
            )

            logger.exception("Erro interno no pipeline clínico")
            raise RuntimeError("Erro interno no processamento clínico.")