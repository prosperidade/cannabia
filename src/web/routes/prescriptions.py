# src/web/routes/prescriptions.py
"""
Fronteira 3 — Endpoints de Prescrição e Fulfillment B2B.

Rotas:
  POST /api/v1/prescriptions/calculate   — Preview de dosagem (IA)
  POST /api/v1/prescriptions/emit        — Emitir prescrição formal
  GET  /api/v1/prescriptions             — Listar prescrições
  GET  /api/v1/prescriptions/<id>        — Detalhe da prescrição
  POST /api/v1/prescriptions/<id>/order  — Criar pedido B2B
  GET  /api/v1/orders                    — Listar pedidos B2B
  PATCH /api/v1/orders/<id>/status       — Atualizar status do pedido
"""

from __future__ import annotations

import logging
from typing import Optional

from flask import Blueprint, g, jsonify, request

from src.services.prescription_service import PrescriptionService
from src.web.routes.api_v1 import (
    _error,
    _json_payload,
    _pagination_args,
    _require_json_csrf,
    _serialize,
    _success,
    api_auth_required,
    api_role_required,
)

logger = logging.getLogger("cannabia.routes.prescriptions")

prescriptions_bp = Blueprint("prescriptions", __name__, url_prefix="/api/v1")
_service = PrescriptionService()


# ═══════════════════════════════════════════════════════════════════════════════
# DOSAGEM — Preview de cálculo de dosagem (IA)
# ═══════════════════════════════════════════════════════════════════════════════

@prescriptions_bp.post("/prescriptions/calculate")
@api_role_required("Admin", "Medico")
def calculate_dosage():
    """
    Calcula dosagem canabinoide para preview.
    O médico pode revisar antes de emitir a prescrição formal.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    if not payload:
        return _error("validation_error", "JSON body é obrigatório.", 422)

    try:
        result = _service.calculate_dosage(payload)
        return _success(result)
    except ValueError as e:
        return _error("validation_error", str(e), 422)
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)
    except Exception as e:
        logger.exception("Erro no cálculo de dosagem")
        return _error("prescriber_error", "Erro ao calcular dosagem.", 500)


# ═══════════════════════════════════════════════════════════════════════════════
# PRESCRIÇÃO — Emissão formal pelo médico
# ═══════════════════════════════════════════════════════════════════════════════

@prescriptions_bp.post("/prescriptions/emit")
@api_role_required("Admin", "Medico")
def emit_prescription():
    """
    Emite prescrição formal após aprovação médica.
    Persiste no banco com CRM, dosagem e protocolo de titulação.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    if not payload:
        return _error("validation_error", "JSON body é obrigatório.", 422)

    try:
        result = _service.emit_prescription(payload)
        return _success(result, status=201)
    except ValueError as e:
        return _error("validation_error", str(e), 422)
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)
    except Exception as e:
        logger.exception("Erro na emissão de prescrição")
        return _error("prescription_error", "Erro ao emitir prescrição.", 500)


# ═══════════════════════════════════════════════════════════════════════════════
# LISTAGEM E DETALHES
# ═══════════════════════════════════════════════════════════════════════════════

@prescriptions_bp.get("/prescriptions")
@api_role_required("Admin", "Medico")
def list_prescriptions():
    """Lista prescrições da clínica, opcionalmente filtradas por paciente."""
    patient_id: Optional[int] = None
    raw = request.args.get("patient_id")
    if raw:
        try:
            patient_id = int(raw)
        except (TypeError, ValueError):
            return _error("validation_error", "patient_id deve ser inteiro.", 422)

    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except (TypeError, ValueError):
        limit = 20

    try:
        prescriptions = _service.list_prescriptions(patient_id=patient_id, limit=limit)
        return _success(_serialize(prescriptions))
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)


@prescriptions_bp.get("/prescriptions/<int:prescription_id>")
@api_role_required("Admin", "Medico")
def get_prescription(prescription_id: int):
    """Detalhe completo de uma prescrição."""
    try:
        prescription = _service.get_prescription(prescription_id)
        if not prescription:
            return _error("not_found", "Prescrição não encontrada.", 404)
        return _success(_serialize(prescription))
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)


# ═══════════════════════════════════════════════════════════════════════════════
# PEDIDOS B2B — Fulfillment para Associações Parceiras
# ═══════════════════════════════════════════════════════════════════════════════

@prescriptions_bp.post("/prescriptions/<int:prescription_id>/order")
@api_role_required("Admin", "Medico")
def create_order(prescription_id: int):
    """
    Cria pedido B2B vinculado a uma prescrição.
    Gera o payload padrão para envio à API da associação parceira.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()

    products = payload.get("products", [])
    if not products:
        return _error("validation_error", "products é obrigatório (lista de produtos).", 422)

    try:
        result = _service.create_b2b_order(
            prescription_id=prescription_id,
            products=products,
            treatment_duration_days=payload.get("treatment_duration_days", 90),
            shipping_address=payload.get("shipping_address"),
            notes=payload.get("notes"),
        )
        return _success(result, status=201)
    except ValueError as e:
        return _error("validation_error", str(e), 422)
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)
    except Exception as e:
        logger.exception("Erro na criação do pedido B2B")
        return _error("order_error", "Erro ao criar pedido B2B.", 500)


@prescriptions_bp.get("/orders")
@api_role_required("Admin", "Medico")
def list_orders():
    """Lista pedidos B2B da clínica."""
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), 100)
    except (TypeError, ValueError):
        limit = 20

    try:
        orders = _service.list_orders(limit=limit)
        return _success(_serialize(orders))
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)


@prescriptions_bp.patch("/orders/<int:order_id>/status")
@api_role_required("Admin", "Medico")
def update_order_status(order_id: int):
    """
    Atualiza status de um pedido B2B.
    Usado para tracking do fulfillment: pending → sent → confirmed → fulfilled.
    """
    csrf_error = _require_json_csrf()
    if csrf_error:
        return csrf_error

    payload = _json_payload()
    new_status = (payload.get("status") or "").strip()
    if not new_status:
        return _error("validation_error", "status é obrigatório.", 422)

    try:
        updated = _service.update_order_status(order_id, new_status)
        if not updated:
            return _error("not_found", "Pedido não encontrado.", 404)
        return _success({"order_id": order_id, "status": new_status, "updated": True})
    except ValueError as e:
        return _error("validation_error", str(e), 422)
    except RuntimeError as e:
        return _error("internal_error", str(e), 500)
