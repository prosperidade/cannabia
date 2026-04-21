"""Fluxo de aprovacao bilateral de documentos regulatorios (F4.7 do SCC).

Implementa a maquina de estados documentada em doc 27 §§2.4 e 8.1:

::

    draft ─submit_to_rt─▶ rt_review ─rt_approve──────▶ legal_review ─legal_approve─▶ approved
                              │                              │
                              │ rt_approve_final             │ legal_reject
                              ▼                              ▼
                           approved                       rejected
                              │
                              │ rt_reject
                              ▼
                           rejected ─submit_to_rt─▶ rt_review (reabertura)

Cada transicao insere uma linha em ``document_review_workflows``
(append-only via trigger), registra um ``signature_hash`` SHA-256 de
``report_id + from_status + to_status + action + actor_user_id +
content_hash + reviewed_at_iso`` e atualiza
``regulatory_reports.status``. Tudo em uma unica transacao.

Assinatura eletronica minima (hash + user_id + timestamp) suficiente
para satisfazer o progresso20 F4.7 — nao substitui ICP-Brasil mas e
verificavel localmente recomputando a partir dos campos da linha.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.infra.database import db_cursor

logger = logging.getLogger("cannabia.document_review")


# ---------------------------------------------------------------------
# Maquina de estados
# ---------------------------------------------------------------------

# Cada acao mapeia para: ({estados de origem permitidos}, estado destino).
# Mantido como dict imutavel para facilitar introspeccao (listing via API).
ALLOWED_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "submit_to_rt":     (frozenset({"draft", "rejected"}), "rt_review"),
    "rt_approve":       (frozenset({"rt_review"}),         "legal_review"),
    "rt_approve_final": (frozenset({"rt_review"}),         "approved"),
    "rt_reject":        (frozenset({"rt_review"}),         "rejected"),
    "legal_approve":    (frozenset({"legal_review"}),      "approved"),
    "legal_reject":     (frozenset({"legal_review"}),      "rejected"),
}

TERMINAL_STATUSES = frozenset({"approved"})

ALL_ACTIONS = tuple(ALLOWED_TRANSITIONS.keys())


# ---------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------

class ReviewError(Exception):
    """Base para erros do fluxo de aprovacao."""


class ReportNotFoundError(ReviewError):
    """regulatory_reports.id nao existe."""


class InvalidTransitionError(ReviewError):
    """Tentativa de aplicar uma acao incompativel com o status atual."""


class InvalidActionError(ReviewError):
    """Action fora de ALLOWED_TRANSITIONS."""


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewStep:
    """Step imutavel do fluxo, ja persistido."""

    id: int
    report_id: int
    from_status: str
    to_status: str
    action: str
    actor_user_id: int
    actor_role: str
    notes: Optional[str]
    content_hash_at_review: str
    signature_hash: str
    reviewed_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ReviewStep":
        return cls(
            id=int(row["id"]),
            report_id=int(row["report_id"]),
            from_status=row["from_status"],
            to_status=row["to_status"],
            action=row["action"],
            actor_user_id=int(row["actor_user_id"]),
            actor_role=row["actor_role"],
            notes=row.get("notes"),
            content_hash_at_review=row["content_hash_at_review"],
            signature_hash=row["signature_hash"],
            reviewed_at=row["reviewed_at"],
        )


# ---------------------------------------------------------------------
# Assinatura
# ---------------------------------------------------------------------

def _compute_signature(
    *,
    report_id: int,
    from_status: str,
    to_status: str,
    action: str,
    actor_user_id: int,
    content_hash: str,
    reviewed_at_iso: str,
) -> str:
    payload = (
        f"{report_id}:{from_status}:{to_status}:{action}:"
        f"{actor_user_id}:{content_hash}:{reviewed_at_iso}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_signature(step: ReviewStep) -> bool:
    """Recomputa ``signature_hash`` a partir dos campos e compara."""
    reviewed_at_iso = step.reviewed_at.isoformat()
    expected = _compute_signature(
        report_id=step.report_id,
        from_status=step.from_status,
        to_status=step.to_status,
        action=step.action,
        actor_user_id=step.actor_user_id,
        content_hash=step.content_hash_at_review,
        reviewed_at_iso=reviewed_at_iso,
    )
    return expected == step.signature_hash


# ---------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------

def _validate_action(action: str, current_status: str) -> str:
    """Valida e devolve o ``to_status`` resultante."""
    spec = ALLOWED_TRANSITIONS.get(action)
    if spec is None:
        raise InvalidActionError(
            f"Acao '{action}' desconhecida. Permitidas: {sorted(ALL_ACTIONS)}."
        )
    allowed_from, to_status = spec
    if current_status not in allowed_from:
        raise InvalidTransitionError(
            f"Acao '{action}' nao permitida a partir de status "
            f"'{current_status}'. Permitido apenas a partir de: "
            f"{sorted(allowed_from)}."
        )
    return to_status


# ---------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------

def get_report_status(report_id: int) -> dict[str, Any]:
    """Retorna status atual + content_hash + last step resumido."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, tenant_id, report_type, version, status,
                   content_hash, current_stage_notes, approved_by, approved_at
              FROM regulatory_reports
             WHERE id = %s
            """,
            (report_id,),
        )
        report = cursor.fetchone()
        if report is None:
            raise ReportNotFoundError(f"Report {report_id} nao encontrado.")

        cursor.execute(
            """
            SELECT id, action, from_status, to_status, actor_user_id,
                   actor_role, reviewed_at
              FROM document_review_workflows
             WHERE report_id = %s
             ORDER BY reviewed_at DESC, id DESC
             LIMIT 1
            """,
            (report_id,),
        )
        last_step = cursor.fetchone()

    return {
        "report": dict(report),
        "last_step": dict(last_step) if last_step else None,
    }


def list_workflow_steps(report_id: int) -> list[ReviewStep]:
    """Historico completo do fluxo, do primeiro ao ultimo."""
    with db_cursor(dictionary=True) as (_, cursor):
        cursor.execute(
            """
            SELECT id, report_id, from_status, to_status, action,
                   actor_user_id, actor_role, notes,
                   content_hash_at_review, signature_hash, reviewed_at
              FROM document_review_workflows
             WHERE report_id = %s
             ORDER BY reviewed_at ASC, id ASC
            """,
            (report_id,),
        )
        return [ReviewStep.from_row(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------
# Transicao principal
# ---------------------------------------------------------------------

def transition(
    report_id: int,
    action: str,
    *,
    actor_user_id: int,
    actor_role: str,
    notes: Optional[str] = None,
) -> ReviewStep:
    """Aplica uma transicao de estado no fluxo de aprovacao.

    Carrega o report, valida action x current_status, calcula
    ``signature_hash``, grava o step em ``document_review_workflows``
    e atualiza ``regulatory_reports.status`` + ``current_stage_notes``
    + (quando destino e 'approved') ``approved_by``/``approved_at``.
    Tudo em uma unica transacao.

    Retorna o :class:`ReviewStep` persistido.
    """
    now = datetime.now(timezone.utc)
    reviewed_at_iso = now.isoformat()

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT id, status, content_hash FROM regulatory_reports "
            "WHERE id = %s FOR UPDATE",
            (report_id,),
        )
        report = cursor.fetchone()
        if report is None:
            raise ReportNotFoundError(f"Report {report_id} nao encontrado.")

        from_status = report["status"]
        content_hash = report["content_hash"]
        to_status = _validate_action(action, from_status)

        signature_hash = _compute_signature(
            report_id=report_id,
            from_status=from_status,
            to_status=to_status,
            action=action,
            actor_user_id=actor_user_id,
            content_hash=content_hash,
            reviewed_at_iso=reviewed_at_iso,
        )

        cursor.execute(
            """
            INSERT INTO document_review_workflows (
                report_id, from_status, to_status, action,
                actor_user_id, actor_role, notes,
                content_hash_at_review, signature_hash, reviewed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, report_id, from_status, to_status, action,
                      actor_user_id, actor_role, notes,
                      content_hash_at_review, signature_hash, reviewed_at
            """,
            (
                report_id, from_status, to_status, action,
                actor_user_id, actor_role, notes,
                content_hash, signature_hash, now,
            ),
        )
        step_row = cursor.fetchone()

        if to_status == "approved":
            cursor.execute(
                """
                UPDATE regulatory_reports
                   SET status = %s,
                       current_stage_notes = %s,
                       approved_by = %s,
                       approved_at = %s
                 WHERE id = %s
                """,
                (to_status, notes, actor_user_id, now, report_id),
            )
        else:
            cursor.execute(
                """
                UPDATE regulatory_reports
                   SET status = %s,
                       current_stage_notes = %s
                 WHERE id = %s
                """,
                (to_status, notes, report_id),
            )
        conn.commit()

    step = ReviewStep.from_row(step_row)
    logger.info(
        "review_transition report=%s %s -> %s action=%s actor=%s",
        report_id, from_status, to_status, action, actor_user_id,
    )
    return step
