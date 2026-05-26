"""Tests pro helper de paginacao canonica (Sprint 2 Track Page)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src.web.pagination import (
    DEFAULT_LIMIT,
    LIMIT_PLUS_ONE_TRICK,
    MAX_LIMIT,
    apply_limit_plus_one,
    paginated_response,
    parse_pagination,
)


def _fake_request(args: dict | None = None, path: str = "/api/v1/x") -> SimpleNamespace:
    """Mock minimo de Flask request."""
    return SimpleNamespace(args=args or {}, path=path)


# ---------------------------------------------------------------------------
# parse_pagination
# ---------------------------------------------------------------------------

def test_parse_pagination_defaults_when_no_args():
    req = _fake_request()
    limit, offset, include_total = parse_pagination(req)
    assert limit == DEFAULT_LIMIT == 50
    assert offset == 0
    assert include_total is False


def test_parse_pagination_explicit_values():
    req = _fake_request({"limit": "30", "offset": "60", "include_total": "1"})
    assert parse_pagination(req) == (30, 60, True)


def test_parse_pagination_legacy_flag_is_ignored():
    """Sprint D Q2: `?legacy=1` foi removido. O param e silenciosamente
    ignorado (nao mais retornado e nao mais loga warning)."""
    req = _fake_request({"legacy": "1"})
    limit, offset, include_total = parse_pagination(req)
    assert (limit, offset, include_total) == (DEFAULT_LIMIT, 0, False)


def test_parse_pagination_limit_above_max_raises(caplog):
    """`limit > MAX_LIMIT` levanta ValueError. Caller mapeia para HTTP 400
    `invalid_limit`."""
    req = _fake_request({"limit": "5000"})
    with caplog.at_level(logging.WARNING, logger="cannabia.web.pagination"):
        with pytest.raises(ValueError, match="excede o maximo"):
            parse_pagination(req)
    assert any("limit_exceeded" in rec.message for rec in caplog.records)
    assert MAX_LIMIT == 200


def test_parse_pagination_at_max_limit_ok():
    """Limit == MAX_LIMIT eh aceito (somente >MAX_LIMIT levanta)."""
    req = _fake_request({"limit": str(MAX_LIMIT)})
    limit, _, _ = parse_pagination(req)
    assert limit == MAX_LIMIT


def test_parse_pagination_invalid_strings_fall_back_to_defaults():
    req = _fake_request({"limit": "abc", "offset": "xyz"})
    limit, offset, _ = parse_pagination(req)
    assert limit == DEFAULT_LIMIT
    assert offset == 0


def test_parse_pagination_negative_limit_raises():
    req = _fake_request({"limit": "-1"})
    with pytest.raises(ValueError):
        parse_pagination(req)


def test_parse_pagination_negative_offset_raises():
    req = _fake_request({"offset": "-5"})
    with pytest.raises(ValueError):
        parse_pagination(req)


def test_parse_pagination_zero_limit_raises():
    req = _fake_request({"limit": "0"})
    with pytest.raises(ValueError):
        parse_pagination(req)


def test_parse_pagination_truthy_variants():
    for raw in ("1", "true", "TRUE", "Yes", "on"):
        req = _fake_request({"include_total": raw})
        _, _, inc = parse_pagination(req)
        assert inc is True, f"falhou pra {raw!r}"
    for raw in ("0", "false", "no", "off", ""):
        req = _fake_request({"include_total": raw})
        _, _, inc = parse_pagination(req)
        assert inc is False, f"falhou pra {raw!r}"


# ---------------------------------------------------------------------------
# paginated_response — envelope
# ---------------------------------------------------------------------------

def test_paginated_response_shape():
    env = paginated_response([{"id": 1}, {"id": 2}], limit=50, offset=0)
    assert set(env.keys()) == {"items", "total", "limit", "offset", "has_more"}
    assert env["items"] == [{"id": 1}, {"id": 2}]
    assert env["total"] is None
    assert env["limit"] == 50
    assert env["offset"] == 0
    assert env["has_more"] is False  # menos rows que limit


def test_paginated_response_has_more_heuristic_when_full_page():
    items = [{"id": i} for i in range(1, 11)]  # 10 itens
    env = paginated_response(items, limit=10, offset=0)
    assert env["has_more"] is True  # full page -> heuristic True


def test_paginated_response_has_more_with_total_known():
    items = list(range(50))
    env = paginated_response(items, limit=50, offset=0, total=120)
    assert env["has_more"] is True

    env2 = paginated_response(items, limit=50, offset=100, total=120)
    assert env2["has_more"] is False  # offset+len >= total


def test_paginated_response_explicit_has_more_overrides():
    items = [1, 2, 3]
    env = paginated_response(items, limit=10, offset=0, has_more=True)
    assert env["has_more"] is True

    env2 = paginated_response(items, limit=3, offset=0, has_more=False)
    # Mesmo com len==limit, override explicito ganha
    assert env2["has_more"] is False


def test_paginated_response_empty_items():
    env = paginated_response([], limit=50, offset=200, total=100)
    assert env["items"] == []
    assert env["has_more"] is False


# ---------------------------------------------------------------------------
# apply_limit_plus_one (LIMIT_PLUS_ONE_TRICK)
# ---------------------------------------------------------------------------

def test_apply_limit_plus_one_truncates_when_overflow():
    rows = [1, 2, 3, 4, 5, 6]  # 6 rows quando limit=5
    items, has_more = apply_limit_plus_one(rows, limit=5)
    assert items == [1, 2, 3, 4, 5]
    assert has_more is True


def test_apply_limit_plus_one_no_overflow():
    rows = [1, 2, 3]
    items, has_more = apply_limit_plus_one(rows, limit=5)
    assert items == [1, 2, 3]
    assert has_more is False


def test_apply_limit_plus_one_exact_limit_means_no_more():
    """Quando o resultset tem exatamente `limit` rows (sem o +1 extra),
    has_more deve ser False — nao houve overflow detectado."""
    rows = [1, 2, 3, 4, 5]
    items, has_more = apply_limit_plus_one(rows, limit=5)
    assert items == [1, 2, 3, 4, 5]
    assert has_more is False


def test_limit_plus_one_alias():
    """LIMIT_PLUS_ONE_TRICK e alias publico de apply_limit_plus_one."""
    assert LIMIT_PLUS_ONE_TRICK is apply_limit_plus_one
