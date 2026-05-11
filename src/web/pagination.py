"""Helpers de paginacao canonica (Sprint 2 Track Page).

Contrato:
    parse_pagination(request) -> (limit, offset, include_total, legacy_mode)
    paginated_response(items, limit, offset, total=None, has_more=None) -> envelope
    bare_legacy_response(items) -> lista nua (escape hatch ?legacy=1)

Envelope canonico:
    {
        "items": [...],
        "total": int | None,   # None se ?include_total=0 (default)
        "limit": int,
        "offset": int,
        "has_more": bool,      # heuristico (limit+1 trick) ou exato com total
    }

Politicas (decisoes coordenador Sprint 2):
    - default_limit = 50; max_limit = 200
    - limit > max_limit -> clamp + logger.warning (Sprint 2 silencia, Sprint 3
      vira HTTP 400)
    - limit < 1 ou offset < 0 -> ValueError
    - ?include_total=1 -> COUNT(*) opt-in (custa)
    - ?legacy=1 -> retorna lista nua, escape hatch por 1 sprint

Helpers de query:
    apply_limit_plus_one(rows, limit) -> (items, has_more) — descarta o
        ultimo row se houve "limit+1", sinal de has_more=True.

Uso pelos repositorios:
    Quando include_total=False: SELECT ... LIMIT (limit + 1) OFFSET offset.
    Quando include_total=True: SELECT COUNT(*) + SELECT ... LIMIT limit.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Sequence, Tuple

logger = logging.getLogger("cannabia.web.pagination")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _coerce_int(raw: Any, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _truthy_flag(raw: Any) -> bool:
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    return s in ("1", "true", "yes", "on")


def parse_pagination(
    request: Any,
    *,
    default_limit: int = DEFAULT_LIMIT,
    max_limit: int = MAX_LIMIT,
) -> Tuple[int, int, bool, bool]:
    """Parseia query params de paginacao da request Flask.

    Retorna (limit, offset, include_total, legacy_mode).

    Raises:
        ValueError: se limit < 1 ou offset < 0 (apos coercao).

    Notas:
        - Sem `?limit` -> usa default (50).
        - `?limit > max_limit` -> clamp + logger.warning. Sprint 2 silencia
          o cliente; Sprint 3 vai retornar HTTP 400.
        - `?include_total=1` -> opt-in pra COUNT(*).
        - `?legacy=1` -> escape hatch (cliente quer lista nua).
    """
    args = request.args if hasattr(request, "args") else request

    raw_limit = args.get("limit") if hasattr(args, "get") else None
    raw_offset = args.get("offset") if hasattr(args, "get") else None
    raw_total = args.get("include_total") if hasattr(args, "get") else None
    raw_legacy = args.get("legacy") if hasattr(args, "get") else None

    limit = _coerce_int(raw_limit, default_limit)
    offset = _coerce_int(raw_offset, 0)
    include_total = _truthy_flag(raw_total)
    legacy_mode = _truthy_flag(raw_legacy)

    if limit < 1:
        raise ValueError(f"limit deve ser >= 1 (recebido {limit})")
    if offset < 0:
        raise ValueError(f"offset deve ser >= 0 (recebido {offset})")

    if limit > max_limit:
        logger.warning(
            "pagination.limit_clamped requested=%s max=%s endpoint=%s",
            limit,
            max_limit,
            getattr(request, "path", "?"),
        )
        limit = max_limit

    return limit, offset, include_total, legacy_mode


def paginated_response(
    items: Sequence[Any],
    *,
    limit: int,
    offset: int,
    total: Optional[int] = None,
    has_more: Optional[bool] = None,
) -> dict:
    """Monta o envelope canonico de paginacao.

    Se `has_more` nao for fornecido, calcula:
        - True se total e conhecido e (offset + len(items)) < total
        - True (heuristico) se len(items) == limit
        - False caso contrario
    """
    items_list = list(items) if not isinstance(items, list) else items

    if has_more is None:
        if total is not None:
            has_more = (offset + len(items_list)) < total
        else:
            has_more = len(items_list) >= limit

    return {
        "items": items_list,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": bool(has_more),
    }


def bare_legacy_response(items: Iterable[Any]) -> list:
    """Compat path: retorna lista nua (sem envelope) pro `?legacy=1`."""
    return list(items)


def apply_limit_plus_one(rows: Sequence[Any], limit: int) -> Tuple[list, bool]:
    """Helper pro padrao "buscar limit+1, descartar o ultimo".

    Usado pelos repositorios quando `include_total=False` (heuristico
    barato pra detectar `has_more` sem rodar COUNT(*)).

    Args:
        rows: resultset de uma query com LIMIT (limit + 1).
        limit: o tamanho de pagina solicitado pelo cliente.

    Returns:
        (items, has_more): items truncado em `limit` rows; has_more=True
        se o resultset original tinha mais que `limit` rows.
    """
    rows_list = list(rows)
    has_more = len(rows_list) > limit
    if has_more:
        rows_list = rows_list[:limit]
    return rows_list, has_more


# Alias publico do trick (mencionado no plano)
LIMIT_PLUS_ONE_TRICK = apply_limit_plus_one
