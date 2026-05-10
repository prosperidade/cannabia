"""
Tests do scripts/retention_audit_logs.py.

Sprint 2 Track LGPD — fecha Divida 2 do BACKLOG_LGPD.md.

Cobre:
1. _env_int parsing (defaults + override).
2. Rows comuns sao archivadas + deletadas apos 90d (default detail).
3. Rows criticos (status security_blocked / error) FICAM ate 365d default.
4. Cleanup do archive: rows com archived_at > 5y sao removidas do archive.
5. Race com inserts durante retention NAO afeta rows novas (filtro por
   created_at < threshold).

Testes que precisam DB skipam se DB local nao reachable.
"""
from __future__ import annotations

import json
import os
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
# Helpers
# =====================================================

def _insert_log_with_age(cur, patient_id: int, request_id: str, days_old: int, status: str = "success"):
    """Insere row com created_at = NOW() - days_old."""
    created = datetime.now(timezone.utc) - timedelta(days=days_old)
    cur.execute(
        """
        INSERT INTO ai_audit_logs (
            patient_id, clinic_id, request_id, user_id, endpoint,
            input_payload, output_payload, status, model,
            prompt_version, prompt_hash, created_at
        ) VALUES (%s, 1, %s, 'test', '/test',
                  %s, %s, %s, 'test-model', 'v1', 'h', %s)
        RETURNING id
        """,
        (patient_id, request_id, json.dumps({"x": 1}), json.dumps({"y": 2}),
         status, created),
    )
    return cur.fetchone()[0]


def _insert_archive_row(cur, patient_id: int, request_id: str, archived_days_ago: int):
    """Insere row direto em ai_audit_logs_archive com archived_at controlado."""
    archived = datetime.now(timezone.utc) - timedelta(days=archived_days_ago)
    created = archived - timedelta(days=10)
    cur.execute(
        """
        INSERT INTO ai_audit_logs_archive (
            patient_id, clinic_id, request_id, user_id, endpoint,
            input_payload, output_payload, status, model,
            prompt_version, prompt_hash, created_at, archived_at
        ) VALUES (%s, 1, %s, 'test', '/test',
                  %s, %s, 'success', 'test-model', 'v1', 'h', %s, %s)
        RETURNING id
        """,
        (patient_id, request_id, json.dumps({"x": 1}), json.dumps({"y": 2}),
         created, archived),
    )
    return cur.fetchone()[0]


@pytest.fixture
def _retention_test_patient():
    pid = 77777
    with db_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO patients (id, clinic_id, name) "
            "VALUES (%s, 1, 'Retention Test') ON CONFLICT (id) DO NOTHING",
            (pid,),
        )
        conn.commit()
    yield pid
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM ai_audit_logs WHERE patient_id = %s", (pid,))
        cur.execute("DELETE FROM ai_audit_logs_archive WHERE patient_id = %s", (pid,))
        cur.execute(
            "DELETE FROM ai_audit_purge_events WHERE executor_host = 'cron' "
            "AND error_summary LIKE 'retention%%'"
        )
        cur.execute("DELETE FROM patients WHERE id = %s", (pid,))
        conn.commit()


# =====================================================
# 1. _env_int
# =====================================================

def test_env_int_default_when_unset(monkeypatch):
    from scripts.retention_audit_logs import _env_int
    monkeypatch.delenv("LGPD_TEST_VAR", raising=False)
    assert _env_int("LGPD_TEST_VAR", 99) == 99


def test_env_int_uses_env_value(monkeypatch):
    from scripts.retention_audit_logs import _env_int
    monkeypatch.setenv("LGPD_TEST_VAR", "42")
    assert _env_int("LGPD_TEST_VAR", 99) == 42


def test_env_int_falls_back_on_garbage(monkeypatch):
    from scripts.retention_audit_logs import _env_int
    monkeypatch.setenv("LGPD_TEST_VAR", "not-a-number")
    assert _env_int("LGPD_TEST_VAR", 99) == 99


# =====================================================
# 2. Threshold: detail = 90d, critical = 365d
# =====================================================

@pytestmark_db
def test_normal_rows_archived_after_detail_threshold(
    _retention_test_patient, monkeypatch
):
    from scripts.retention_audit_logs import archive_and_delete

    pid = _retention_test_patient

    with db_cursor() as (conn, cur):
        # Row de 100d atras, status success → DEVE ir pro archive (detail=90)
        old_id = _insert_log_with_age(cur, pid, "ret-old", 100, "success")
        # Row de 30d atras, status success → fica no hot (jovem)
        young_id = _insert_log_with_age(cur, pid, "ret-young", 30, "success")
        conn.commit()

    archived, failed = archive_and_delete(detail_days=90, critical_days=365)
    assert archived >= 1
    assert failed == 0

    # Old foi pro archive
    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM ai_audit_logs_archive WHERE id = %s", (old_id,))
        assert cur.fetchone() is not None
        cur.execute("SELECT 1 FROM ai_audit_logs WHERE id = %s", (old_id,))
        assert cur.fetchone() is None
        # Young ficou no hot
        cur.execute("SELECT 1 FROM ai_audit_logs WHERE id = %s", (young_id,))
        assert cur.fetchone() is not None


@pytestmark_db
def test_critical_rows_kept_until_critical_threshold(
    _retention_test_patient, monkeypatch
):
    from scripts.retention_audit_logs import archive_and_delete

    pid = _retention_test_patient

    with db_cursor() as (conn, cur):
        # Row criticO de 100d (security_blocked) → NAO vai (critical=365)
        critical_id = _insert_log_with_age(
            cur, pid, "ret-crit-young", 100, "security_blocked"
        )
        # Row error de 400d → vai (passou de critical=365)
        critical_old_id = _insert_log_with_age(
            cur, pid, "ret-err-old", 400, "error"
        )
        conn.commit()

    archived, _ = archive_and_delete(detail_days=90, critical_days=365)
    assert archived >= 1

    with db_cursor() as (_, cur):
        # Critical recente (100d) PRECISA continuar no hot
        cur.execute("SELECT 1 FROM ai_audit_logs WHERE id = %s", (critical_id,))
        assert cur.fetchone() is not None, (
            "rows criticos NAO podem sair antes de critical_days"
        )
        # Critical velho (400d) foi pro archive
        cur.execute("SELECT 1 FROM ai_audit_logs_archive WHERE id = %s", (critical_old_id,))
        assert cur.fetchone() is not None


# =====================================================
# 3. Archive cleanup
# =====================================================

@pytestmark_db
def test_archive_cleanup_removes_rows_past_ttl(_retention_test_patient):
    from scripts.retention_audit_logs import cleanup_archive

    pid = _retention_test_patient

    with db_cursor() as (conn, cur):
        old_arch = _insert_archive_row(cur, pid, "arch-old", 2000)  # 5+ years
        recent_arch = _insert_archive_row(cur, pid, "arch-recent", 100)
        conn.commit()

    deleted = cleanup_archive(archive_days=1825)  # 5y default
    assert deleted >= 1

    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM ai_audit_logs_archive WHERE id = %s", (old_arch,))
        assert cur.fetchone() is None, "row arquivado ha 2000d devia ter sido deletado"
        cur.execute("SELECT 1 FROM ai_audit_logs_archive WHERE id = %s", (recent_arch,))
        assert cur.fetchone() is not None, "row arquivado ha 100d nao pode ser deletado"


# =====================================================
# 4. Race com insert durante retention
# =====================================================

@pytestmark_db
def test_inserts_during_retention_window_are_safe(_retention_test_patient):
    """Row inserido com created_at = NOW() (jovem) NUNCA pode ser apagado
    pelo retention, mesmo se rodar concorrente."""
    from scripts.retention_audit_logs import archive_and_delete

    pid = _retention_test_patient

    with db_cursor() as (conn, cur):
        # Row de 100d (vai sair)
        _insert_log_with_age(cur, pid, "race-old", 100, "success")
        # Row novissimo (NAO pode sair)
        new_id = _insert_log_with_age(cur, pid, "race-new", 0, "success")
        conn.commit()

    archive_and_delete(detail_days=90, critical_days=365)

    with db_cursor() as (_, cur):
        cur.execute("SELECT 1 FROM ai_audit_logs WHERE id = %s", (new_id,))
        assert cur.fetchone() is not None, (
            "row recem-inserido durante retention NAO pode ser apagado"
        )


# =====================================================
# 5. Run end-to-end + event grava cron host
# =====================================================

@pytestmark_db
def test_run_records_purge_event_with_cron_host(
    _retention_test_patient, monkeypatch
):
    from scripts.retention_audit_logs import run

    pid = _retention_test_patient

    with db_cursor() as (conn, cur):
        _insert_log_with_age(cur, pid, "run-e2e", 200, "success")
        conn.commit()

    monkeypatch.setenv("LGPD_AUDIT_RETENTION_DAYS_DETAIL", "90")
    monkeypatch.setenv("LGPD_AUDIT_RETENTION_DAYS_CRITICAL", "365")
    monkeypatch.setenv("LGPD_AUDIT_ARCHIVE_RETENTION_DAYS", "1825")

    stats = run()
    assert stats["event_id"] is not None
    assert stats["archived"] >= 1

    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT executor_user, executor_host, finished_at "
            "FROM ai_audit_purge_events WHERE id = %s",
            (stats["event_id"],),
        )
        row = cur.fetchone()
    assert row[0] == "cron"
    assert row[1] is not None
    assert row[2] is not None
