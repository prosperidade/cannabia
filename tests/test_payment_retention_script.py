"""
Tests do scripts/retention_payment_data.py (FIN-2, doc 30 R2).

Cobre:
1. _env_int parsing (default + override + lixo).
2. Kill switch: main() no-op quando PAYMENT_PURGE_ENABLED nao setado.
3. raw_payload de payment_transactions e zerado apos cutoff (DB-gated).
4. body/headers de payment_webhook_log sao zerados apos cutoff (DB-gated).
5. Rows jovens (received_at recente) NAO sao tocados (DB-gated).
6. run() registra evento em payment_data_purge_events (DB-gated).

Testes que precisam DB skipam se DB local nao reachable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta

import pytest

from src.infra.database import db_cursor


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark_db = pytest.mark.skipif(
    not _db_reachable(), reason="DB local nao alcancavel"
)


# =====================================================
# 1. _env_int
# =====================================================

def test_env_int_default_when_unset(monkeypatch):
    from scripts.retention_payment_data import _env_int
    monkeypatch.delenv("PAYMENT_TEST_VAR", raising=False)
    assert _env_int("PAYMENT_TEST_VAR", 90) == 90


def test_env_int_uses_env_value(monkeypatch):
    from scripts.retention_payment_data import _env_int
    monkeypatch.setenv("PAYMENT_TEST_VAR", "30")
    assert _env_int("PAYMENT_TEST_VAR", 90) == 30


def test_env_int_falls_back_on_garbage(monkeypatch):
    from scripts.retention_payment_data import _env_int
    monkeypatch.setenv("PAYMENT_TEST_VAR", "abc")
    assert _env_int("PAYMENT_TEST_VAR", 90) == 90


# =====================================================
# 2. Kill switch
# =====================================================

def test_main_is_noop_when_disabled(monkeypatch):
    from scripts.retention_payment_data import main
    monkeypatch.delenv("PAYMENT_PURGE_ENABLED", raising=False)
    # nao deve chamar run(); retorna 0
    assert main() == 0


# =====================================================
# DB-gated: redacao real
# =====================================================

@pytest.fixture
def _payment_request_id():
    """Cria uma payment_request descartavel e limpa no teardown."""
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO payment_requests (tenant_id, clinic_id, external_id,
                                          amount_cents, method, provider, status)
            VALUES (99991, 1, %s, 5000, 'pix', 'manual', 'pending')
            RETURNING id
            """,
            (f"cbn-ret-test-{datetime.now(timezone.utc).timestamp()}",),
        )
        rid = cur.fetchone()["id"]
        conn.commit()
    yield rid
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM payment_transactions WHERE payment_request_id = %s", (rid,))
        cur.execute("DELETE FROM payment_requests WHERE id = %s", (rid,))
        cur.execute(
            "DELETE FROM payment_webhook_log WHERE provider = 'ret-test-provider'"
        )
        conn.commit()


def _insert_tx(request_id: int, days_old: int, payload: dict) -> int:
    received = datetime.now(timezone.utc) - timedelta(days=days_old)
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO payment_transactions (
                payment_request_id, tenant_id, provider, provider_event_id,
                event_type, status, amount_cents, raw_payload, received_at
            ) VALUES (%s, 99991, 'ret-test-provider', %s, 'charge.paid',
                      'succeeded', 5000, %s::jsonb, %s)
            RETURNING id
            """,
            (request_id, f"evt-{days_old}-{received.timestamp()}",
             json.dumps(payload), received),
        )
        tid = cur.fetchone()["id"]
        conn.commit()
    return tid


@pytestmark_db
def test_old_transaction_payload_is_redacted(_payment_request_id):
    from scripts.retention_payment_data import redact_transaction_payloads

    old_tid = _insert_tx(_payment_request_id, 200, {"payer_document": "12345678901"})
    young_tid = _insert_tx(_payment_request_id, 10, {"payer_document": "98765432100"})

    redacted = redact_transaction_payloads(retention_days=90)
    assert redacted >= 1

    with db_cursor(dictionary=True) as (_, cur):
        cur.execute("SELECT raw_payload FROM payment_transactions WHERE id = %s", (old_tid,))
        assert cur.fetchone()["raw_payload"] == {}, "payload velho devia estar zerado"
        cur.execute("SELECT raw_payload FROM payment_transactions WHERE id = %s", (young_tid,))
        assert cur.fetchone()["raw_payload"] != {}, "payload jovem NAO pode ser tocado"


@pytestmark_db
def test_old_webhook_log_is_redacted():
    from scripts.retention_payment_data import redact_webhook_logs

    old = datetime.now(timezone.utc) - timedelta(days=200)
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            """
            INSERT INTO payment_webhook_log (provider, received_at, signature_ok,
                                             status_code, body, headers, error_message)
            VALUES ('ret-test-provider', %s, TRUE, 200, %s::jsonb, %s::jsonb, 'boom')
            RETURNING id
            """,
            (old, json.dumps({"cpf": "12345678901"}), json.dumps({"X-Sig": "abc"})),
        )
        log_id = cur.fetchone()["id"]
        conn.commit()

    try:
        redacted = redact_webhook_logs(retention_days=90)
        assert redacted >= 1
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT body, headers, error_message, provider, status_code "
                "FROM payment_webhook_log WHERE id = %s",
                (log_id,),
            )
            row = cur.fetchone()
        assert row["body"] == {}
        assert row["headers"] == {}
        assert row["error_message"] is None
        # metadados de auditoria preservados
        assert row["provider"] == "ret-test-provider"
        assert row["status_code"] == 200
    finally:
        with db_cursor() as (conn, cur):
            cur.execute("DELETE FROM payment_webhook_log WHERE id = %s", (log_id,))
            conn.commit()


@pytestmark_db
def test_run_records_purge_event(_payment_request_id, monkeypatch):
    from scripts.retention_payment_data import run

    _insert_tx(_payment_request_id, 200, {"payer_document": "12345678901"})
    monkeypatch.setenv("PAYMENT_DATA_RETENTION_DAYS", "90")

    stats = run()
    assert stats["event_id"] is not None
    assert stats["rows_failed"] == 0

    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute(
            "SELECT executor_host, finished_at, dry_run "
            "FROM payment_data_purge_events WHERE id = %s",
            (stats["event_id"],),
        )
        row = cur.fetchone()
        # limpa o evento do teste
        cur.execute("DELETE FROM payment_data_purge_events WHERE id = %s", (stats["event_id"],))
        conn.commit()
    assert row["executor_host"] is not None
    assert row["finished_at"] is not None
    assert row["dry_run"] is False
