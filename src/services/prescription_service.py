# src/services/prescription_service.py
"""
Fronteira 3 — Serviço de Prescrição e Fulfillment B2B.

Orquestra o fluxo completo:
  1. Validação + Guardrails
  2. Billing check
  3. Prescriber (Rules Engine + LLM)
  4. Persistência da prescrição
  5. Geração do pedido B2B para associação parceira
  6. Audit logging
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import g
from pydantic import ValidationError

from src.ai.guardrails import validate_input
from src.ai.prescriber import calculate_safety_limits, run_prescriber
from src.ai.pricing import calculate_cost
from src.ai.schemas import (
    AdministrationRoute,
    AssociationProduct,
    B2BOrderPayload,
    DosageInput,
    DosageRecommendation,
    OrderStatus,
    PrescriptionPayload,
    ProductSpectrum,
)
from src.infra.database import db_cursor
from src.repositories.ai_audit_repository import save_ai_audit_log
from src.repositories.anamnesis_repository import get_report
from src.repositories.patient_repository import get_or_create_patient_by_name
from src.services.billing_service import (
    BillingLimitExceeded,
    check_ai_allowance,
    record_ai_usage,
)
from src.services.prescription_contract import build_dosage_input_or_raise, build_prescription_contract

logger = logging.getLogger("cannabia.prescription")


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY LAYER — Persistência de prescrições e pedidos B2B
# ═══════════════════════════════════════════════════════════════════════════════

def _save_prescription(
    clinic_id: int,
    patient_id: int,
    doctor_user_id: int,
    doctor_name: str,
    doctor_crm: str,
    recommendation: DosageRecommendation,
    safety_limits: dict,
    custom_notes: Optional[str],
    validity_days: int,
    regulatory_condition: str = "nenhuma",
    clinical_justification: Optional[str] = None,
) -> int:
    """Persiste a prescrição no banco e retorna o prescription_id."""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescriptions (
                clinic_id, patient_id, doctor_user_id, doctor_name, doctor_crm,
                cannabinoid_ratio, spectrum, administration_route,
                concentration_mg_ml, max_daily_mg,
                titration_protocol, clinical_rationale,
                contraindications, drug_interactions,
                monitoring_checkpoints, confidence_score,
                evidence_sources, safety_limits,
                custom_notes, validity_days,
                regulatory_condition, clinical_justification, status,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, 'active',
                NOW()
            )
            RETURNING id
            """,
            (
                clinic_id, patient_id, doctor_user_id, doctor_name, doctor_crm,
                recommendation.cannabinoid_ratio,
                recommendation.spectrum.value,
                recommendation.administration_route.value,
                recommendation.concentration_mg_ml,
                recommendation.max_daily_mg,
                json.dumps([s.model_dump() for s in recommendation.titration_protocol]),
                recommendation.clinical_rationale,
                json.dumps(recommendation.contraindications),
                json.dumps(recommendation.drug_interactions),
                json.dumps(recommendation.monitoring_checkpoints),
                recommendation.confidence_score,
                json.dumps(recommendation.evidence_sources),
                json.dumps(safety_limits),
                custom_notes,
                validity_days,
                regulatory_condition,
                clinical_justification,
            ),
        )
        row = cur.fetchone()
        return row[0]


def _save_b2b_order(
    order_payload: B2BOrderPayload,
) -> int:
    """Persiste o pedido B2B no banco e retorna o order_id."""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO b2b_orders (
                order_ref, prescription_id, clinic_id, patient_id,
                patient_name, doctor_crm,
                products, dosage_summary,
                cannabinoid_ratio, administration_route,
                total_daily_mg, treatment_duration_days,
                shipping_address, notes, status,
                created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, %s,
                NOW()
            )
            RETURNING id
            """,
            (
                order_payload.order_id,
                order_payload.prescription_id,
                order_payload.clinic_id,
                order_payload.patient_id,
                order_payload.patient_name,
                order_payload.doctor_crm,
                json.dumps([p.model_dump() for p in order_payload.products]),
                order_payload.dosage_summary,
                order_payload.cannabinoid_ratio,
                order_payload.administration_route.value,
                order_payload.total_daily_mg,
                order_payload.treatment_duration_days,
                json.dumps(order_payload.shipping_address) if order_payload.shipping_address else None,
                order_payload.notes,
                order_payload.status.value,
            ),
        )
        row = cur.fetchone()
        return row[0]


def _get_prescription(clinic_id: int, prescription_id: int) -> Optional[dict]:
    """Busca prescrição por ID."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, clinic_id, patient_id, doctor_user_id, doctor_name, doctor_crm,
                   cannabinoid_ratio, spectrum, administration_route,
                   concentration_mg_ml, max_daily_mg,
                   titration_protocol, clinical_rationale,
                   contraindications, drug_interactions,
                   monitoring_checkpoints, confidence_score,
                   evidence_sources, safety_limits,
                   custom_notes, validity_days, status,
                   regulatory_condition, clinical_justification,
                   created_at
            FROM prescriptions
            WHERE id = %s AND clinic_id = %s
            """,
            (prescription_id, clinic_id),
        )
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))


def _list_prescriptions(clinic_id: int, patient_id: Optional[int] = None, limit: int = 20) -> List[dict]:
    """Lista prescrições da clínica, opcionalmente filtradas por paciente."""
    with db_cursor() as cur:
        if patient_id:
            cur.execute(
                """
                SELECT id, patient_id, doctor_name, doctor_crm,
                       cannabinoid_ratio, spectrum, concentration_mg_ml,
                       max_daily_mg, confidence_score, status,
                       regulatory_condition, created_at
                FROM prescriptions
                WHERE clinic_id = %s AND patient_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (clinic_id, patient_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, patient_id, doctor_name, doctor_crm,
                       cannabinoid_ratio, spectrum, concentration_mg_ml,
                       max_daily_mg, confidence_score, status,
                       regulatory_condition, created_at
                FROM prescriptions
                WHERE clinic_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (clinic_id, limit),
            )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _list_b2b_orders(clinic_id: int, limit: int = 20) -> List[dict]:
    """Lista pedidos B2B da clínica."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT id, order_ref, prescription_id, patient_name,
                   doctor_crm, dosage_summary, cannabinoid_ratio,
                   total_daily_mg, treatment_duration_days,
                   status, created_at
            FROM b2b_orders
            WHERE clinic_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (clinic_id, limit),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def _update_order_status(clinic_id: int, order_id: int, new_status: str) -> bool:
    """Atualiza status de um pedido B2B."""
    with db_cursor() as cur:
        cur.execute(
            """
            UPDATE b2b_orders
            SET status = %s, updated_at = NOW()
            WHERE id = %s AND clinic_id = %s
            RETURNING id
            """,
            (new_status, order_id, clinic_id),
        )
        return cur.fetchone() is not None


def _record_prescription_consent(
    *,
    clinic_id: int,
    prescription_id: int,
    patient_id: int,
    prescriber_user_id: Optional[int],
    prescriber_crm: Optional[str],
    prescriber_habilitado: bool,
    tcle_accepted: Optional[bool],
    details: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Registra o TCLE/consentimento vinculado à prescrição (REG-1015 / RDC
    1.015/2026). `tcle_accepted=None` = pendente de captura (assinatura é UI futura)."""
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            INSERT INTO prescription_consents
                (clinic_id, prescription_id, patient_id, prescriber_user_id,
                 prescriber_crm, prescriber_habilitado, tcle_accepted, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                clinic_id, prescription_id, patient_id, prescriber_user_id,
                prescriber_crm, prescriber_habilitado, tcle_accepted,
                json.dumps(details or {}, default=str),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE LAYER — Orquestração do fluxo completo
# ═══════════════════════════════════════════════════════════════════════════════

class PrescriptionService:

    def calculate_dosage(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula dosagem para um paciente.
        Retorna a recomendação + limites de segurança (sem persistir).
        Usado para preview antes do médico aprovar.
        """
        start = time.time()
        clinic_id: Optional[int] = getattr(g, "clinic_id", None)
        request_id: Optional[str] = getattr(g, "request_id", None)
        user_id: Optional[str] = getattr(g, "user_id", None)

        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto da request")

        # Billing
        allowance = check_ai_allowance(clinic_id)
        if not allowance.allowed:
            raise BillingLimitExceeded(
                clinic_id=clinic_id,
                resource="ai_requests",
                current=allowance.requests_used,
                limit=allowance.requests_limit,
            )

        # Guardrails
        guardrail_result = validate_input(data)
        if not guardrail_result.passed:
            raise ValueError("Possível tentativa de prompt injection detectada.")

        report = None
        attendance_id = data.get("attendance_id")
        if attendance_id not in (None, ""):
            try:
                report = get_report(clinic_id, int(attendance_id))
            except (TypeError, ValueError):
                raise ValueError("attendance_id deve ser inteiro.")
            if not report:
                raise ValueError("Atendimento informado não foi encontrado.")

        dosage_payload = build_dosage_input_or_raise(report=report, overrides=data)
        contract = build_prescription_contract(report=report, overrides=data)

        # Validação
        try:
            dosage_input = DosageInput(**dosage_payload)
        except ValidationError as e:
            raise ValueError(f"Dados inválidos: {e}")

        # Prescriber
        recommendation, limits, tokens = run_prescriber(dosage_input)

        # Billing — registro
        total_tokens = tokens.get("total_tokens", 0)
        estimated_cost = calculate_cost("gpt-4o-mini", tokens.get("input_tokens", 0), tokens.get("output_tokens", 0))
        record_ai_usage(clinic_id=clinic_id, tokens_used=total_tokens, estimated_cost_usd=estimated_cost)

        # Audit
        elapsed_ms = int((time.time() - start) * 1000)
        save_ai_audit_log(
            clinic_id=clinic_id,
            patient_id=None,
            request_id=request_id,
            endpoint="/api/v1/prescriptions/calculate",
            user_id=user_id,
            input_payload=data,
            output_payload=recommendation.model_dump(),
            status="success",
            error_message=None,
            model="gpt-4o-mini",
            prompt_version="prescriber_v1.0",
            prompt_hash=hashlib.sha256(b"prescriber_v1.0").hexdigest(),
            input_tokens=tokens.get("input_tokens"),
            output_tokens=tokens.get("output_tokens"),
            total_tokens=total_tokens,
            clinical_time_ms=None,
            treatment_time_ms=None,
            report_time_ms=None,
            total_time_ms=elapsed_ms,
            estimated_cost_usd=estimated_cost,
        )

        return {
            "prescription_contract": contract,
            "dosage_input": dosage_payload,
            "recommendation": recommendation.model_dump(),
            "safety_limits": asdict(limits),
            "token_usage": tokens,
            "estimated_cost_usd": estimated_cost,
            "processing_time_ms": elapsed_ms,
        }

    def emit_prescription(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Médico aprova e emite prescrição formal.
        Persiste no banco e gera o payload B2B.
        """
        clinic_id: Optional[int] = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto da request")

        try:
            payload = PrescriptionPayload(**data, clinic_id=clinic_id)
        except ValidationError as e:
            raise ValueError(f"Dados inválidos: {e}")

        # Persistir prescrição
        prescription_id = _save_prescription(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            doctor_user_id=payload.doctor_user_id,
            doctor_name=payload.doctor_name,
            doctor_crm=payload.doctor_crm,
            recommendation=payload.dosage_recommendation,
            safety_limits={},
            custom_notes=payload.custom_notes,
            validity_days=payload.validity_days,
            regulatory_condition=payload.regulatory_condition.value,
            clinical_justification=payload.clinical_justification,
        )

        # Gerar protocolo de titulação resumido para B2B
        first_step = payload.dosage_recommendation.titration_protocol[0]
        dosage_summary = (
            f"{first_step.drops_per_dose} gotas "
            f"{first_step.doses_per_day}x/dia "
            f"{payload.dosage_recommendation.administration_route.value} "
            f"{payload.dosage_recommendation.spectrum.value} "
            f"{payload.dosage_recommendation.concentration_mg_ml}mg/mL"
        )

        logger.info(
            "Prescrição #%d emitida: CRM=%s, patient=%d, ratio=%s",
            prescription_id, payload.doctor_crm, payload.patient_id,
            payload.dosage_recommendation.cannabinoid_ratio,
        )

        # CLI-3 / 29.2 R3 — verificação ANVISA no caminho de emissão.
        # Decisão registrada: *warning auditado*, NÃO bloqueante (o médico é o
        # decisor; a aprovação regulatória é prerrogativa da Anvisa). Alertas são
        # auditados e devolvidos no payload para exibição.
        rec = payload.dosage_recommendation
        anvisa_compliance = {"compliant": True, "issues": [], "checked_norms": []}
        try:
            from src.ai.agents.regulatorio import check_anvisa

            anvisa_compliance = check_anvisa({
                "cannabinoid_ratio": rec.cannabinoid_ratio,
                "administration_route": rec.administration_route.value,
                "max_daily_mg": rec.max_daily_mg,
                "regulatory_condition": payload.regulatory_condition.value,
            })
            if not anvisa_compliance["compliant"]:
                logger.warning(
                    "Prescrição #%d emitida com alertas ANVISA: %s",
                    prescription_id, anvisa_compliance["issues"],
                )
                from src.infra.audit import log_audit_event

                log_audit_event(
                    action="prescription_anvisa_warning",
                    resource_type="prescription",
                    resource_id=str(prescription_id),
                    details={
                        "issues": anvisa_compliance["issues"],
                        "checked_norms": anvisa_compliance["checked_norms"],
                        "cannabinoid_ratio": rec.cannabinoid_ratio,
                        "administration_route": rec.administration_route.value,
                        "max_daily_mg": rec.max_daily_mg,
                    },
                    clinic_id=clinic_id,
                )
        except Exception:
            logger.exception(
                "Falha no check ANVISA da prescrição #%d (emissão não bloqueada)",
                prescription_id,
            )

        # REG-1015 / RDC 1.015/2026 (JÁ EM VIGOR) — prontidão mínima no fluxo de
        # prescrição: validação de prescritor habilitado + registro de TCLE
        # vinculado à prescrição. Não bloqueia a emissão (prontidão auditada); a
        # UI de assinatura e a validação plena do conselho ficam para depois.
        reg_1015 = {"tcle_recorded": False, "prescriber_habilitado": None}
        try:
            from src.ai.agents.regulatorio import validate_prescriber_habilitation

            habil = validate_prescriber_habilitation(payload.doctor_crm, payload.doctor_user_id)
            tcle_accepted = data.get("tcle_accepted")  # None = pendente de captura
            consent_id = _record_prescription_consent(
                clinic_id=clinic_id,
                prescription_id=prescription_id,
                patient_id=payload.patient_id,
                prescriber_user_id=payload.doctor_user_id,
                prescriber_crm=payload.doctor_crm,
                prescriber_habilitado=habil["habilitado"],
                tcle_accepted=tcle_accepted,
                details={"habilitation": habil, "norm_ref": "RDC 1.015/2026"},
            )
            reg_1015 = {
                "tcle_recorded": consent_id is not None,
                "consent_id": consent_id,
                "prescriber_habilitado": habil["habilitado"],
                "tcle_accepted": tcle_accepted,
                "pending_revalidation": True,
            }
            if not habil["habilitado"]:
                logger.warning(
                    "Prescrição #%d: prescritor sem habilitação confirmada (%s)",
                    prescription_id, habil.get("reason"),
                )
                from src.infra.audit import log_audit_event

                log_audit_event(
                    action="prescription_prescriber_unverified",
                    resource_type="prescription",
                    resource_id=str(prescription_id),
                    details=habil,
                    clinic_id=clinic_id,
                )
        except Exception:
            logger.exception(
                "Falha no registro REG-1015 da prescrição #%d (emissão não bloqueada)",
                prescription_id,
            )

        # REG-3 / RDCs 2026 — registro estruturado da condição grave/debilitante
        # / cuidados paliativos + justificativa do médico (auditada). É o
        # pré-requisito de elegibilidade para THC > 0,2% (REG-4). NUNCA bloqueia
        # a emissão (B6): a ausência de condição habilitante em prescrição com
        # THC vira *warning auditado*, não impedimento.
        reg_3 = {
            "regulatory_condition": payload.regulatory_condition.value,
            "has_justification": bool((payload.clinical_justification or "").strip()),
        }
        try:
            from src.ai.prescriber import _thc_fraction_from_ratio
            from src.infra.audit import log_audit_event

            thc_present = _thc_fraction_from_ratio(rec.cannabinoid_ratio) > 0
            condition_informed = payload.regulatory_condition.value != "nenhuma"
            justification_present = bool((payload.clinical_justification or "").strip())

            if condition_informed or justification_present:
                log_audit_event(
                    action="prescription_regulatory_condition",
                    resource_type="prescription",
                    resource_id=str(prescription_id),
                    details={
                        "regulatory_condition": payload.regulatory_condition.value,
                        "clinical_justification": payload.clinical_justification,
                        "cannabinoid_ratio": rec.cannabinoid_ratio,
                        "thc_present": thc_present,
                        "norm_ref": "RDCs 2026 (REG-3)",
                    },
                    clinic_id=clinic_id,
                )

            if thc_present and not condition_informed:
                reg_3["warning"] = (
                    "Prescrição com THC sem condição grave/debilitante ou "
                    "paliativa registrada (REG-3/REG-4). Registre a classificação "
                    "e a justificativa do médico."
                )
                logger.warning("Prescrição #%d: %s", prescription_id, reg_3["warning"])
                log_audit_event(
                    action="prescription_regulatory_condition_missing",
                    resource_type="prescription",
                    resource_id=str(prescription_id),
                    details={
                        "cannabinoid_ratio": rec.cannabinoid_ratio,
                        "regulatory_condition": payload.regulatory_condition.value,
                        "norm_ref": "RDCs 2026 (REG-3/REG-4)",
                    },
                    clinic_id=clinic_id,
                )
        except Exception:
            logger.exception(
                "Falha no registro REG-3 da prescrição #%d (emissão não bloqueada)",
                prescription_id,
            )

        return {
            "prescription_id": prescription_id,
            "dosage_summary": dosage_summary,
            "status": "active",
            "anvisa_compliance": anvisa_compliance,
            "reg_1015": reg_1015,
            "reg_3": reg_3,
        }

    def create_b2b_order(
        self,
        prescription_id: int,
        products: List[Dict[str, Any]],
        treatment_duration_days: int = 90,
        shipping_address: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Gera pedido B2B para associação parceira a partir de uma prescrição existente.
        """
        clinic_id: Optional[int] = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto da request")

        prescription = _get_prescription(clinic_id, prescription_id)
        if not prescription:
            raise ValueError(f"Prescrição #{prescription_id} não encontrada.")

        if prescription["status"] != "active":
            raise ValueError(f"Prescrição #{prescription_id} não está ativa (status: {prescription['status']}).")

        # Parsear produtos
        parsed_products = [AssociationProduct(**p) for p in products]

        # Calcular total diário da primeira fase da titulação
        titration = json.loads(prescription["titration_protocol"]) if isinstance(prescription["titration_protocol"], str) else prescription["titration_protocol"]
        first_step = titration[0] if titration else {}
        total_daily_mg = first_step.get("total_daily_mg", 0)

        # Montar dosage_summary
        dosage_summary = (
            f"{first_step.get('drops_per_dose', 0)} gotas "
            f"{first_step.get('doses_per_day', 0)}x/dia "
            f"{prescription['administration_route']} "
            f"{prescription['spectrum']} "
            f"{prescription['concentration_mg_ml']}mg/mL"
        )

        order_ref = f"ORD-{uuid.uuid4().hex[:12].upper()}"

        order_payload = B2BOrderPayload(
            order_id=order_ref,
            prescription_id=prescription_id,
            clinic_id=clinic_id,
            patient_id=prescription["patient_id"],
            patient_name="",  # Será preenchido pelo frontend
            doctor_crm=prescription["doctor_crm"],
            products=parsed_products,
            dosage_summary=dosage_summary,
            cannabinoid_ratio=prescription["cannabinoid_ratio"],
            administration_route=AdministrationRoute(prescription["administration_route"]),
            total_daily_mg=total_daily_mg,
            treatment_duration_days=treatment_duration_days,
            shipping_address=shipping_address,
            notes=notes,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        order_id = _save_b2b_order(order_payload)

        logger.info(
            "Pedido B2B #%d criado: ref=%s, prescription=%d, products=%d",
            order_id, order_ref, prescription_id, len(parsed_products),
        )

        return {
            "order_id": order_id,
            "order_ref": order_ref,
            "prescription_id": prescription_id,
            "dosage_summary": dosage_summary,
            "products_count": len(parsed_products),
            "status": "pending",
            "b2b_payload": order_payload.model_dump(mode="json"),
        }

    def get_prescription(self, prescription_id: int) -> Optional[dict]:
        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto")
        return _get_prescription(clinic_id, prescription_id)

    def list_prescriptions(self, patient_id: Optional[int] = None, limit: int = 20) -> List[dict]:
        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto")
        return _list_prescriptions(clinic_id, patient_id, limit)

    def list_orders(self, limit: int = 20) -> List[dict]:
        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto")
        return _list_b2b_orders(clinic_id, limit)

    def update_order_status(self, order_id: int, new_status: str) -> bool:
        clinic_id = getattr(g, "clinic_id", None)
        if clinic_id is None:
            raise RuntimeError("clinic_id não encontrado no contexto")
        valid = {s.value for s in OrderStatus}
        if new_status not in valid:
            raise ValueError(f"Status inválido. Válidos: {valid}")
        return _update_order_status(clinic_id, order_id, new_status)
