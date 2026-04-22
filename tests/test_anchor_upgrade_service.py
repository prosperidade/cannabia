"""Testes do anchor_upgrade_service (F5.7 do SCC).

Usa db_cursor mockado + probes injetadas — sem rede, sem DB real.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.services import anchor_upgrade_service as ups
from src.services.anchor_upgrade_service import (
    UpgradeOutcome,
    UpgradeStatus,
    list_pending_anchors,
    run_upgrade_sweep,
    upgrade_anchor,
)


# ---------------------------------------------------------------------
# Fake DB harness
# ---------------------------------------------------------------------

class _FakeCursor:
    """Cursor com fila pre-programada de respostas para cada execute()."""

    def __init__(self):
        self._queue: list = []
        self.executes: list[tuple[str, tuple]] = []

    def program(self, *items) -> "_FakeCursor":
        self._queue.extend(items)
        return self

    def execute(self, sql, params=()):
        self.executes.append((sql, tuple(params)))
        self._last = self._queue.pop(0) if self._queue else None

    def fetchone(self):
        val = getattr(self, "_last", None)
        if isinstance(val, list):
            return val[0] if val else None
        return val

    def fetchall(self):
        val = getattr(self, "_last", None)
        if isinstance(val, list):
            return list(val)
        return [val] if val is not None else []


class _FakeConn:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class _FakeCtx:
    def __init__(self, cursor, conn):
        self._c = cursor
        self._conn = conn

    def __enter__(self):
        return (self._conn, self._c)

    def __exit__(self, *exc):
        return False


def _install_db(monkeypatch, cursor, conn):
    monkeypatch.setattr(
        "src.services.anchor_upgrade_service.db_cursor",
        lambda dictionary=True: _FakeCtx(cursor, conn),
    )


NOW = datetime(2026, 4, 21, 18, tzinfo=timezone.utc)


def _pending_row(anchor_id: int, *, network: str = "polygon",
                 anchored_at: datetime | None = None) -> dict:
    return {
        "id": anchor_id,
        "tenant_id": 1,
        "anchor_scope": "tenant",
        "blockchain_network": network,
        "merkle_root": "a" * 64,
        "transaction_id": "0x" + "bc" * 32,
        "proof_uri": f"polygon://amoy/tx/0xbc{anchor_id}",
        "proof_hash": "c" * 64,
        "anchored_at": anchored_at or (NOW - timedelta(minutes=30)),
        "verified_at": None,
        "verification_status": "pending",
    }


# ---------------------------------------------------------------------
# list_pending_anchors
# ---------------------------------------------------------------------

class TestListPendingAnchors:
    def test_retorna_rows_em_ordem(self, monkeypatch):
        cursor = _FakeCursor().program([
            _pending_row(1, anchored_at=NOW - timedelta(hours=2)),
            _pending_row(2, anchored_at=NOW - timedelta(minutes=20)),
        ])
        _install_db(monkeypatch, cursor, _FakeConn())
        rows = list_pending_anchors(now=NOW)
        assert [r["id"] for r in rows] == [1, 2]
        sql, params = cursor.executes[0]
        assert "verification_status = 'pending'" in sql
        assert "ORDER BY anchored_at ASC" in sql
        # threshold respeita min_age_seconds
        assert isinstance(params[0], datetime)


# ---------------------------------------------------------------------
# upgrade_anchor — caminhos
# ---------------------------------------------------------------------

class TestUpgradeAnchor:
    def _install_for_upgrade(self, monkeypatch, anchor_row: dict,
                             status_row: dict | None = None):
        """Programa (SELECT status+lock), (SELECT full row), (opcional UPDATE)."""
        lock_row = status_row or {
            "id": anchor_row["id"],
            "blockchain_network": anchor_row["blockchain_network"],
            "verification_status": anchor_row["verification_status"],
            "anchored_at": anchor_row["anchored_at"],
            "verified_at": anchor_row["verified_at"],
        }
        cursor = _FakeCursor().program(lock_row, anchor_row, None)
        conn = _FakeConn()
        _install_db(monkeypatch, cursor, conn)
        return cursor, conn

    def test_confirmed_atualiza_status_e_block_info(self, monkeypatch):
        row = _pending_row(42, network="polygon")
        cursor, conn = self._install_for_upgrade(monkeypatch, row)
        probes = {"polygon": lambda r: {
            "confirmed": True,
            "block_number": 12345678,
            "block_timestamp": NOW,
            "proof_uri": "polygon://amoy/tx/0xconfirmed",
            "proof_hash": "deadbeef" * 8,
        }}
        outcome = upgrade_anchor(42, probes=probes, now=NOW)
        assert outcome.new_status == UpgradeStatus.CONFIRMED
        assert outcome.block_number == 12345678
        assert outcome.verified_at == NOW
        assert conn.commits == 1
        # 3 executes: SELECT lock + SELECT full + UPDATE
        assert len(cursor.executes) == 3
        assert "UPDATE blockchain_anchors" in cursor.executes[2][0]
        assert "'confirmed'" in cursor.executes[2][0]

    def test_still_pending_nao_mexe_no_db(self, monkeypatch):
        row = _pending_row(7)
        cursor, conn = self._install_for_upgrade(monkeypatch, row)
        probes = {"polygon": lambda r: {"confirmed": False, "error": None}}
        outcome = upgrade_anchor(7, probes=probes, now=NOW)
        assert outcome.new_status == UpgradeStatus.STILL_PENDING
        # so 2 SELECTs, nenhum UPDATE
        assert len(cursor.executes) == 2
        assert conn.commits == 0

    def test_failed_quando_erro_e_idade_maxima(self, monkeypatch):
        old_row = _pending_row(9, anchored_at=NOW - timedelta(hours=72))
        cursor, conn = self._install_for_upgrade(monkeypatch, old_row)
        probes = {"polygon": lambda r: {
            "confirmed": False, "error": "tx not found",
        }}
        outcome = upgrade_anchor(9, probes=probes, now=NOW)
        assert outcome.new_status == UpgradeStatus.FAILED
        assert "tx not found" in outcome.error
        assert conn.commits == 1
        assert "'failed'" in cursor.executes[2][0]

    def test_erro_em_anchor_recente_fica_pending(self, monkeypatch):
        recent_row = _pending_row(11, anchored_at=NOW - timedelta(minutes=10))
        cursor, conn = self._install_for_upgrade(monkeypatch, recent_row)
        probes = {"polygon": lambda r: {
            "confirmed": False, "error": "still confirming",
        }}
        outcome = upgrade_anchor(11, probes=probes, now=NOW)
        assert outcome.new_status == UpgradeStatus.STILL_PENDING
        assert conn.commits == 0

    def test_ja_confirmed_retorna_skipped(self, monkeypatch):
        cursor = _FakeCursor().program({
            "id": 5, "blockchain_network": "polygon",
            "verification_status": "confirmed",
            "anchored_at": NOW, "verified_at": NOW,
        })
        _install_db(monkeypatch, cursor, _FakeConn())
        outcome = upgrade_anchor(5, probes={}, now=NOW)
        assert outcome.new_status == UpgradeStatus.SKIPPED
        assert outcome.previous_status == "confirmed"

    def test_sem_probe_para_network(self, monkeypatch):
        row = _pending_row(13, network="unknown_chain")
        self._install_for_upgrade(monkeypatch, row)
        outcome = upgrade_anchor(13, probes={}, now=NOW)
        assert outcome.new_status == UpgradeStatus.SKIPPED
        assert "unknown_chain" in outcome.error

    def test_anchor_nao_encontrado(self, monkeypatch):
        cursor = _FakeCursor().program(None)
        _install_db(monkeypatch, cursor, _FakeConn())
        with pytest.raises(ValueError, match="nao encontrado"):
            upgrade_anchor(999, probes={"polygon": lambda r: {}})

    def test_probe_exception_vira_still_pending(self, monkeypatch):
        row = _pending_row(15)
        cursor, conn = self._install_for_upgrade(monkeypatch, row)
        def _boom(r):
            raise RuntimeError("network blew up")
        probes = {"polygon": _boom}
        outcome = upgrade_anchor(15, probes=probes, now=NOW)
        assert outcome.new_status == UpgradeStatus.STILL_PENDING
        assert "probe exception" in outcome.error


# ---------------------------------------------------------------------
# run_upgrade_sweep
# ---------------------------------------------------------------------

class TestSweep:
    def test_processa_todos_candidates(self, monkeypatch):
        rows = [_pending_row(1), _pending_row(2), _pending_row(3)]
        # Cada upgrade_anchor faz 2-3 execs + list faz 1.
        # Para nao reprogramar cursor toda hora, monkeypatch diretamente.
        monkeypatch.setattr(
            "src.services.anchor_upgrade_service.list_pending_anchors",
            lambda **kw: rows,
        )
        calls = []
        def _fake_upgrade(anchor_id, *, probes=None, now=None):
            calls.append(anchor_id)
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status="pending",
                new_status=UpgradeStatus.CONFIRMED,
                verified_at=now, block_number=None, block_timestamp=None,
            )
        monkeypatch.setattr(
            "src.services.anchor_upgrade_service.upgrade_anchor", _fake_upgrade
        )
        outcomes = run_upgrade_sweep(probes=None, now=NOW)
        assert calls == [1, 2, 3]
        assert all(o.new_status == UpgradeStatus.CONFIRMED for o in outcomes)

    def test_exception_em_um_nao_afeta_outros(self, monkeypatch):
        rows = [_pending_row(1), _pending_row(2)]
        monkeypatch.setattr(
            "src.services.anchor_upgrade_service.list_pending_anchors",
            lambda **kw: rows,
        )
        def _fake_upgrade(anchor_id, *, probes=None, now=None):
            if anchor_id == 1:
                raise RuntimeError("boom")
            return UpgradeOutcome(
                anchor_id=anchor_id, previous_status="pending",
                new_status=UpgradeStatus.STILL_PENDING,
                verified_at=None, block_number=None, block_timestamp=None,
            )
        monkeypatch.setattr(
            "src.services.anchor_upgrade_service.upgrade_anchor", _fake_upgrade
        )
        outcomes = run_upgrade_sweep(now=NOW)
        assert len(outcomes) == 2
        assert outcomes[0].error is not None and "boom" in outcomes[0].error
        assert outcomes[1].new_status == UpgradeStatus.STILL_PENDING


# ---------------------------------------------------------------------
# Default probes (lazy import sanity)
# ---------------------------------------------------------------------

class TestDefaultProbes:
    def test_ots_probe_sem_pacote_instalado_retorna_pending(self):
        """_default_ots_probe deve lidar gracilmente quando o pacote
        opentimestamps-client nao esta instalado (caso comum em CI)."""
        row = _pending_row(1, network="bitcoin_ots")
        result = ups._default_ots_probe(row)
        assert result["confirmed"] is False
        assert result.get("error") is not None

    def test_polygon_probe_sem_pacote_instalado_retorna_pending(self):
        row = _pending_row(1, network="polygon")
        result = ups._default_polygon_probe(row)
        assert result["confirmed"] is False
        assert result.get("error") is not None
