"""
Tests do OBS-1 (doc 30): verificacao tripla automatica de backup.

Cobre:
1. sample_restore_check (3o gate) — sucesso, DDL insuficiente, pg_restore falho.
2. _alert nunca crasha sem Sentry.
3. main() no-op quando BACKUP_VERIFY_ENABLED desligado (kill switch).
4. run() em falha: grava heartbeat success=False e dispara alerta.
5. record_event grava heartbeat (DB-gated).
6. run() end-to-end com pg_dump real (DB + binarios gated).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


def _pg_tools_available() -> bool:
    if shutil.which("pg_dump") and shutil.which("pg_restore"):
        return True
    return Path("C:/Program Files/PostgreSQL/18/bin/pg_dump.exe").exists()


db_gate = pytest.mark.skipif(not _db_reachable(), reason="DB local nao alcancavel")
e2e_gate = pytest.mark.skipif(
    not (_db_reachable() and _pg_tools_available()),
    reason="DB e/ou pg_dump/pg_restore indisponiveis",
)


def _fake_proc(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


# =====================================================
# 1. sample_restore_check
# =====================================================

def _many_ddl(n: int) -> str:
    return "\n".join(f"CREATE TABLE t{i} (id int);" for i in range(n))


def test_sample_restore_check_ok():
    from scripts import backup_postgres_validated as bpv

    with patch.object(bpv, "_resolve_binary", return_value="pg_restore"), \
         patch.object(bpv, "_run", return_value=_fake_proc(stdout=_many_ddl(40))):
        n = bpv.sample_restore_check(Path("x.dump"), None)
    assert n == 40


def test_sample_restore_check_rejects_too_few_ddl():
    from scripts import backup_postgres_validated as bpv

    with patch.object(bpv, "_resolve_binary", return_value="pg_restore"), \
         patch.object(bpv, "_run", return_value=_fake_proc(stdout=_many_ddl(3))):
        with pytest.raises(RuntimeError, match="amostra"):
            bpv.sample_restore_check(Path("x.dump"), None)


def test_sample_restore_check_rejects_pg_restore_failure():
    from scripts import backup_postgres_validated as bpv

    with patch.object(bpv, "_resolve_binary", return_value="pg_restore"), \
         patch.object(bpv, "_run", return_value=_fake_proc(returncode=1, stderr="corrupt")):
        with pytest.raises(RuntimeError, match="amostra"):
            bpv.sample_restore_check(Path("x.dump"), None)


# =====================================================
# 2. _alert
# =====================================================

def test_alert_never_raises(monkeypatch):
    from scripts.backup_verify import _alert
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    _alert("teste de alerta")  # nao deve levantar


# =====================================================
# 3. kill switch
# =====================================================

def test_main_noop_when_disabled(monkeypatch):
    from scripts.backup_verify import main
    monkeypatch.delenv("BACKUP_VERIFY_ENABLED", raising=False)
    with patch("scripts.backup_verify.run") as run:
        assert main() == 0
        run.assert_not_called()


# =====================================================
# 4. run() failure path: heartbeat + alerta
# =====================================================

def test_run_failure_records_event_and_alerts(monkeypatch):
    import scripts.backup_verify as bv
    monkeypatch.setenv("BACKUP_VERIFY_PATH", "/path/que/nao/existe.dump")

    with patch.object(bv, "record_event", return_value=123) as rec, \
         patch.object(bv, "_alert") as alert:
        stats = bv.run()

    assert stats["success"] is False
    assert stats["error_message"]
    rec.assert_called_once()
    assert rec.call_args.kwargs["success"] is False
    alert.assert_called_once()


# =====================================================
# 5. record_event (DB-gated)
# =====================================================

@db_gate
def test_record_event_persists_heartbeat():
    from scripts.backup_verify import record_event

    event_id = record_event(
        success=True,
        dump_path="/tmp/test.dump",
        dump_bytes=4096,
        restore_list_lines=1000,
        sample_restore_ddl_lines=200,
        sha256="deadbeef",
        error_message=None,
    )
    assert event_id is not None
    try:
        with db_cursor(dictionary=True) as (_, cur):
            cur.execute(
                "SELECT success, dump_bytes, executor_host, finished_at "
                "FROM backup_verification_events WHERE id = %s",
                (event_id,),
            )
            row = cur.fetchone()
        assert row["success"] is True
        assert row["dump_bytes"] == 4096
        assert row["executor_host"] is not None
        assert row["finished_at"] is not None
    finally:
        with db_cursor() as (conn, cur):
            cur.execute("DELETE FROM backup_verification_events WHERE id = %s", (event_id,))
            conn.commit()


# =====================================================
# 6. End-to-end com pg_dump real (DB + binarios)
# =====================================================

@e2e_gate
def test_run_end_to_end_real_dump(monkeypatch, tmp_path):
    import scripts.backup_verify as bv
    from scripts import backup_postgres_validated as bpv

    # checksum em tmp para nao sujar o CHECKSUMS.txt versionado
    monkeypatch.setattr(bpv, "DEFAULT_CHECKSUM_FILE", tmp_path / "CHECKSUMS.txt")
    monkeypatch.setattr(bpv, "DEFAULT_BACKUP_DIR", tmp_path)
    if not shutil.which("pg_dump"):
        monkeypatch.setenv("PG_BIN", "C:/Program Files/PostgreSQL/18/bin")

    stats = bv.run()

    assert stats["success"] is True, stats.get("error_message")
    assert stats["dump_bytes"] > 1024
    assert stats["sample_restore_ddl_lines"] >= 20
    assert stats["event_id"] is not None

    # cleanup do heartbeat
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM backup_verification_events WHERE id = %s", (stats["event_id"],))
        conn.commit()
