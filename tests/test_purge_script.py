"""
Tests do scripts/purge_audit_pii_pre_a3.py.

Sprint 2 Track LGPD — fecha Divida 1 do BACKLOG_LGPD.md.

Cobre:
1. CLI: dry-run default, --commit muda mode, mutually exclusive.
2. Dry-run NAO modifica DB (input/output_payload preservados).
3. Commit mode: redige PII conhecida (CPF, email, patient_name) + grava
   ai_audit_purge_events com finished_at.
4. Idempotencia: rodar 2x → segunda run zero novos updates (filtro por
   ai_audit_purge_processed_ids funciona).
5. Resume apos falha simulada: rows ja processadas nao re-processam.
6. Snapshot table criada com TTL noticavel via nome (data ISO).

Testes que precisam DB skipam se DB local nao reachable.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.infra.database import db_cursor


# =====================================================
# Helpers
# =====================================================

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


CUTOFF_TEST_ISO = "2026-05-10T17:00:00+00:00"
CUTOFF_TEST_DT = datetime(2026, 5, 10, 17, 0, 0, tzinfo=timezone.utc)


def _insert_pre_a3_log(
    cur, patient_id: int, request_id: str, created_at, payload_input, payload_output
):
    """Insere row de teste em ai_audit_logs com created_at controlado.

    Bypassa save_ai_audit_log de proposito — a graca do teste eh ter
    PII em texto plano (estado pre-A.3).
    """
    cur.execute(
        """
        INSERT INTO ai_audit_logs (
            patient_id, clinic_id, request_id, user_id, endpoint,
            input_payload, output_payload, status, model,
            prompt_version, prompt_hash, created_at
        ) VALUES (%s, 1, %s, 'test', '/test',
                  %s, %s, 'success', 'test-model',
                  'v1', 'h', %s)
        RETURNING id
        """,
        (
            patient_id,
            request_id,
            json.dumps(payload_input, ensure_ascii=False),
            json.dumps(payload_output, ensure_ascii=False),
            created_at,
        ),
    )
    return cur.fetchone()[0]


@pytest.fixture
def _purge_test_patient():
    """Garante patient + cleanup das tables tocadas pelos testes."""
    pid = 88888
    rid_prefix = "purge-test-"
    with db_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO patients (id, clinic_id, name) "
            "VALUES (%s, 1, 'Purge Test') ON CONFLICT (id) DO NOTHING",
            (pid,),
        )
        conn.commit()
    yield pid, rid_prefix
    with db_cursor() as (conn, cur):
        # 1) Remove processed_ids referenciando rows deste patient
        cur.execute(
            "DELETE FROM ai_audit_purge_processed_ids "
            "WHERE audit_log_id IN (SELECT id FROM ai_audit_logs WHERE patient_id = %s)",
            (pid,),
        )
        # 2) Drop processed_ids dos events que vamos apagar (FK)
        cur.execute(
            "DELETE FROM ai_audit_purge_processed_ids "
            "WHERE purge_event_id IN ("
            "  SELECT id FROM ai_audit_purge_events WHERE cutoff_timestamp = %s"
            ")",
            (CUTOFF_TEST_ISO,),
        )
        cur.execute("DELETE FROM ai_audit_logs WHERE patient_id = %s", (pid,))
        cur.execute(
            "DELETE FROM ai_audit_purge_events WHERE cutoff_timestamp = %s",
            (CUTOFF_TEST_ISO,),
        )
        cur.execute("DELETE FROM patients WHERE id = %s", (pid,))
        conn.commit()


# =====================================================
# 1. CLI parsing
# =====================================================

def test_parse_args_default_is_dry_run():
    from scripts.purge_audit_pii_pre_a3 import _parse_args

    args = _parse_args([])
    assert args.dry_run is True
    assert args.commit is False
    assert args.cutoff == "2026-05-10T17:00:00+00:00"
    assert args.batch_size == 1000
    assert args.max_batches is None


def test_parse_args_commit_flips_dry_run():
    from scripts.purge_audit_pii_pre_a3 import _parse_args

    args = _parse_args(["--commit"])
    assert args.dry_run is False
    assert args.commit is True


def test_parse_args_dry_run_and_commit_mutually_exclusive():
    from scripts.purge_audit_pii_pre_a3 import _parse_args

    with pytest.raises(SystemExit):
        _parse_args(["--dry-run", "--commit"])


def test_parse_args_custom_cutoff_and_batch():
    from scripts.purge_audit_pii_pre_a3 import _parse_args

    args = _parse_args(
        ["--cutoff", "2025-01-01T00:00:00+00:00", "--batch-size", "50",
         "--max-batches", "3", "--clinic-id", "42"]
    )
    assert args.cutoff == "2025-01-01T00:00:00+00:00"
    assert args.batch_size == 50
    assert args.max_batches == 3
    assert args.clinic_id == 42


# =====================================================
# 2. Snapshot table naming
# =====================================================

def test_snapshot_name_is_dated():
    from scripts.purge_audit_pii_pre_a3 import _snapshot_table_name

    fixed = datetime(2026, 5, 10, 17, 0, 0, tzinfo=timezone.utc)
    assert _snapshot_table_name(fixed) == "ai_audit_logs_pre_redact_backup_20260510"


# =====================================================
# 3. DB integration: dry-run nao modifica
# =====================================================

@pytestmark_db
def test_dry_run_does_not_modify_db(_purge_test_patient):
    from scripts.purge_audit_pii_pre_a3 import run_purge, _parse_args

    pid, prefix = _purge_test_patient
    pre_cutoff = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)

    payload_in = {
        "patient_name": "Joao Silva",
        "main_complaint": "Dor cronica. CPF 123.456.789-00.",
    }
    payload_out = {"clinical_analysis": {"summary": "Email: x@y.com"}}

    with db_cursor() as (conn, cur):
        row_id = _insert_pre_a3_log(
            cur, pid, prefix + "dry1", pre_cutoff, payload_in, payload_out
        )
        conn.commit()

    args = _parse_args([])  # dry-run default
    args.clinic_id = 1
    stats = run_purge(args)

    # DB nao deve ter mudado
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT input_payload, output_payload FROM ai_audit_logs WHERE id = %s",
            (row_id,),
        )
        row = cur.fetchone()

    assert row[0]["patient_name"] == "Joao Silva", (
        "dry-run NAO pode mutar input_payload"
    )
    assert "123.456.789-00" in row[0]["main_complaint"]
    assert "x@y.com" in row[1]["clinical_analysis"]["summary"]
    # Estatisticas reportam scan
    assert stats["dry_run"] is True
    assert stats["estimated_total"] >= 1


# =====================================================
# 4. Commit mode: redige PII + registra evento
# =====================================================

@pytestmark_db
def test_commit_redacts_known_pii_and_records_event(_purge_test_patient):
    from scripts.purge_audit_pii_pre_a3 import run_purge, _parse_args

    pid, prefix = _purge_test_patient
    pre_cutoff = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)

    payload_in = {
        "patient_name": "Maria Souza",
        "main_complaint": "Paciente: Maria Souza. CPF 999.888.777-66.",
    }
    payload_out = {"clinical_analysis": {"summary": "Contato: maria@test.com"}}

    with db_cursor() as (conn, cur):
        row_id = _insert_pre_a3_log(
            cur, pid, prefix + "commit1", pre_cutoff, payload_in, payload_out
        )
        conn.commit()

    args = _parse_args(["--commit", "--batch-size", "10"])
    args.clinic_id = 1
    stats = run_purge(args)

    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT input_payload, output_payload FROM ai_audit_logs WHERE id = %s",
            (row_id,),
        )
        row = cur.fetchone()

    # patient_name virou marker
    assert row[0]["patient_name"] == "[REDACTED:key]"
    # CPF capturado pelo regex em string-leaf
    assert "999.888.777-66" not in row[0]["main_complaint"]
    assert "[CPF_REDACTED]" in row[0]["main_complaint"]
    # Email capturado em output
    assert "maria@test.com" not in row[1]["clinical_analysis"]["summary"]
    assert "[EMAIL_REDACTED]" in row[1]["clinical_analysis"]["summary"]

    # Evento gravado
    assert stats["event_id"] is not None
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT dry_run, finished_at, rows_updated FROM ai_audit_purge_events "
            "WHERE id = %s",
            (stats["event_id"],),
        )
        ev = cur.fetchone()
    assert ev[0] is False  # dry_run = False
    assert ev[1] is not None  # finished_at set
    assert ev[2] >= 1


# =====================================================
# 5. Idempotencia: 2a run zero novos updates
# =====================================================

@pytestmark_db
def test_idempotent_second_run_zero_new_updates(_purge_test_patient):
    from scripts.purge_audit_pii_pre_a3 import run_purge, _parse_args

    pid, prefix = _purge_test_patient
    pre_cutoff = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)

    payload_in = {"patient_name": "Pedro", "free": "Email: p@x.com"}

    with db_cursor() as (conn, cur):
        _insert_pre_a3_log(
            cur, pid, prefix + "idem1", pre_cutoff, payload_in, None
        )
        conn.commit()

    args = _parse_args(["--commit", "--batch-size", "10"])
    args.clinic_id = 1
    stats1 = run_purge(args)
    assert stats1["rows_updated"] >= 1

    # 2a run: filtro por processed_ids deve excluir
    args2 = _parse_args(["--commit", "--batch-size", "10"])
    args2.clinic_id = 1
    stats2 = run_purge(args2)
    assert stats2["estimated_total"] == 0
    assert stats2["rows_updated"] == 0


# =====================================================
# 6. Resume apos falha: rows ja processadas nao re-processam
# =====================================================

@pytestmark_db
def test_resume_skips_already_processed_rows(_purge_test_patient):
    """Simula crash: marca alguns IDs em processed_ids manualmente,
    roda commit, verifica que SO os non-processed sao tocados."""
    from scripts.purge_audit_pii_pre_a3 import (
        run_purge, _parse_args, open_purge_event,
    )

    pid, prefix = _purge_test_patient
    pre_cutoff = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)

    ids: list[int] = []
    with db_cursor() as (conn, cur):
        for i in range(3):
            row_id = _insert_pre_a3_log(
                cur,
                pid,
                f"{prefix}resume-{i}",
                pre_cutoff,
                {"patient_name": f"Nome{i}", "free": f"x{i}@y.com"},
                None,
            )
            ids.append(row_id)
        conn.commit()

    # Marca o primeiro como ja processado por um event ficticio
    fake_event_id = open_purge_event(
        CUTOFF_TEST_ISO, dry_run=False, batch_size=10
    )
    with db_cursor() as (conn, cur):
        cur.execute(
            "INSERT INTO ai_audit_purge_processed_ids "
            "(audit_log_id, purge_event_id) VALUES (%s, %s)",
            (ids[0], fake_event_id),
        )
        conn.commit()

    args = _parse_args(["--commit", "--batch-size", "10"])
    args.clinic_id = 1
    stats = run_purge(args)

    # Pelo menos os 2 nao-processados foram pegos
    assert stats["rows_updated"] >= 2

    # Row[0] (ja marcado) deve estar intacto — input nao foi sanitizado
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT input_payload FROM ai_audit_logs WHERE id = %s", (ids[0],)
        )
        row = cur.fetchone()
    # Estado pre-A.3 preservado:
    assert row[0]["patient_name"] == "Nome0"

    # Os outros foram sanitizados
    with db_cursor() as (_, cur):
        cur.execute(
            "SELECT input_payload FROM ai_audit_logs WHERE id IN (%s, %s)",
            (ids[1], ids[2]),
        )
        rows = cur.fetchall()
    for row in rows:
        assert row[0]["patient_name"] == "[REDACTED:key]"
