"""Endpoint publico de verificacao de ancoragem Merkle (F5.5 do SCC).

Permite que terceiros (ANVISA, auditor independente, associado, imprensa)
verifiquem que um evento especifico esta coberto por uma ancoragem em
blockchain publica, sem precisar de autenticacao.

Contrato (doc 26 §6):

    GET /api/v1/public/anchors/<int:tenant_id>/verify
        ?table=<event_table>
        &event_id=<int>

Retorna a lista de ancoragens relevantes ao tenant informado (escopo
``tenant`` ou ``global``) que cobrem o evento, cada uma com a
``merkle_path``, a ``merkle_root`` e os identificadores da transacao
on-chain suficientes para verificacao independente.

O servidor tambem faz uma verificacao local (``server_verified``) usando
``verify_merkle_proof`` — se vier ``false`` em producao, indica
adulteracao do banco (o merkle_root esta "travado" em blockchain no
modo real; no modo mock de F5.2 a seguranca e fraca, mas a propriedade
matematica da verificacao local continua util).

Sem auth, sem CSRF — tenancy.py deve incluir ``/api/v1/public`` em
``PUBLIC_PREFIXES`` para nao exigir contexto de clinica.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from flask import Blueprint, request

from src.services.anchoring_service import (
    EVENT_TABLES,
    get_mappings_for_event,
    verify_merkle_proof,
)
from src.web.routes.api_v1 import _error, _success

logger = logging.getLogger("cannabia.public_anchors")

public_anchors_bp = Blueprint(
    "public_anchors", __name__, url_prefix="/api/v1/public/anchors"
)


def _parse_event_id(raw: Optional[str]):
    if raw is None or raw == "":
        return None, _error(
            "missing_event_id",
            "Parametro 'event_id' obrigatorio.",
            400,
        )
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, _error(
            "invalid_event_id",
            "Parametro 'event_id' deve ser inteiro.",
            400,
        )


def _parse_table(raw: Optional[str]):
    if raw is None or raw == "":
        return None, _error(
            "missing_table",
            "Parametro 'table' obrigatorio.",
            400,
        )
    if raw not in EVENT_TABLES:
        return None, _error(
            "invalid_table",
            f"'table' deve ser uma das: {sorted(EVENT_TABLES)}.",
            422,
        )
    return raw, None


def _is_relevant(mapping: dict[str, Any], requested_tenant_id: int) -> bool:
    """Ancoragens 'global' cobrem todos os tenants; 'tenant' deve bater."""
    scope = mapping.get("anchor_scope")
    if scope == "global":
        return True
    return mapping.get("tenant_id") == requested_tenant_id


def _build_anchor_response(mapping: dict[str, Any]) -> dict[str, Any]:
    """Converte um row retornado por ``get_mappings_for_event`` em dict
    estavel para JSON + executa verificacao local."""
    merkle_path = mapping.get("merkle_path") or []
    merkle_root = mapping["merkle_root"]
    event_hash = mapping["event_hash"]
    try:
        server_verified = verify_merkle_proof(event_hash, merkle_path, merkle_root)
    except Exception as exc:                       # noqa: BLE001
        logger.warning(
            "verify_failed anchor_id=%s event_table=%s event_id=%s err=%s",
            mapping.get("anchor_id"),
            mapping.get("event_table"),
            mapping.get("event_id"),
            exc,
        )
        server_verified = False

    return {
        "anchor_id": mapping["anchor_id"],
        "anchor_scope": mapping["anchor_scope"],
        "tenant_id": mapping.get("tenant_id"),
        "blockchain_network": mapping["blockchain_network"],
        "transaction_id": mapping["transaction_id"],
        "merkle_root": merkle_root,
        "event_hash": event_hash,
        "merkle_path": merkle_path,
        "covered_from": mapping.get("covered_from"),
        "covered_until": mapping.get("covered_until"),
        "anchored_at": mapping.get("anchored_at"),
        "verified_at": mapping.get("verified_at"),
        "verification_status": mapping.get("verification_status"),
        "server_verified": server_verified,
    }


@public_anchors_bp.route("/<int:tenant_id>/verify", methods=["GET"])
def verify_event(tenant_id: int):
    """Retorna ancoragens relevantes ao ``tenant_id`` que cobrem
    ``(table, event_id)``.

    Erros:
      - 400 missing/invalid event_id
      - 400 missing table
      - 422 table fora da whitelist
      - 404 nenhuma ancoragem relevante encontrada
    """
    event_id, err = _parse_event_id(request.args.get("event_id"))
    if err is not None:
        return err

    event_table, err = _parse_table(request.args.get("table"))
    if err is not None:
        return err

    mappings = get_mappings_for_event(event_table, event_id)
    relevant = [m for m in mappings if _is_relevant(m, tenant_id)]

    if not relevant:
        return _error(
            "anchor_not_found",
            "Nenhuma ancoragem encontrada para o evento informado.",
            404,
            details={
                "tenant_id": tenant_id,
                "event_table": event_table,
                "event_id": event_id,
            },
        )

    anchors = [_build_anchor_response(m) for m in relevant]
    all_verified = all(a["server_verified"] for a in anchors)

    logger.info(
        "anchor_verified tenant=%s table=%s event=%s anchors=%d all_verified=%s",
        tenant_id, event_table, event_id, len(anchors), all_verified,
    )

    return _success(
        {
            "request": {
                "tenant_id": tenant_id,
                "event_table": event_table,
                "event_id": event_id,
            },
            "anchors": anchors,
            "all_verified": all_verified,
        }
    )
