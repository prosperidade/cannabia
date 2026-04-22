"""Testes do wrapper Polygon (F5.4 do SCC).

Sem dependencia de ``web3`` real — usa client injetado via Protocol
``anchor(scope, scope_id, merkle_root, period_start, period_end) -> tx_hash``.
Cobre tambem o dispatcher em anchoring_service para provider='polygon'.
"""

from __future__ import annotations

import hashlib

import pytest

from src.integrations import polygon_anchor as polygon
from src.integrations.polygon_anchor import (
    PolygonError,
    PolygonReceipt,
    PolygonSubmissionError,
    PolygonUnavailableError,
    scope_id_to_bytes32,
    submit_to_polygon,
)


class _FakeClient:
    """Client fake que devolve tx_hash deterministico por hash do input."""

    def __init__(self, tx_hash: str = "0x" + "ab" * 32,
                 raise_exc: Exception | None = None):
        self._tx_hash = tx_hash
        self._raise = raise_exc
        self.calls: list[dict] = []

    def anchor(self, scope, scope_id, merkle_root, period_start, period_end):
        self.calls.append({
            "scope": scope, "scope_id": scope_id,
            "merkle_root": merkle_root,
            "period_start": period_start, "period_end": period_end,
        })
        if self._raise:
            raise self._raise
        return self._tx_hash


# ---------------------------------------------------------------------
# scope_id_to_bytes32
# ---------------------------------------------------------------------

class TestScopeIdConversion:
    def test_global_e_zero_bytes32(self):
        assert scope_id_to_bytes32("global", None) == b"\x00" * 32

    def test_tenant_e_big_endian(self):
        result = scope_id_to_bytes32("tenant", 42)
        assert len(result) == 32
        assert int.from_bytes(result, "big") == 42

    def test_project(self):
        result = scope_id_to_bytes32("project", None, project_id=7)
        assert int.from_bytes(result, "big") == 7

    def test_tenant_sem_tenant_id(self):
        with pytest.raises(PolygonError, match="tenant_id"):
            scope_id_to_bytes32("tenant", None)

    def test_project_sem_project_id(self):
        with pytest.raises(PolygonError, match="project_id"):
            scope_id_to_bytes32("project", tenant_id=1, project_id=None)

    def test_scope_invalido(self):
        with pytest.raises(PolygonError, match="invalido"):
            scope_id_to_bytes32("galaxy", 1)


# ---------------------------------------------------------------------
# submit_to_polygon
# ---------------------------------------------------------------------

class TestSubmitToPolygon:
    ROOT = "a" * 64
    TX = "0x" + "ab" * 32

    def test_happy_path_tenant(self, monkeypatch):
        monkeypatch.setenv("POLYGON_NETWORK", "amoy")
        client = _FakeClient(tx_hash=self.TX)
        receipt = submit_to_polygon(
            self.ROOT,
            scope="tenant", tenant_id=42,
            period_start=1700000000, period_end=1700086400,
            client=client,
        )
        assert isinstance(receipt, PolygonReceipt)
        assert receipt.transaction_id == self.TX
        assert receipt.proof_uri == f"polygon://amoy/tx/{self.TX}"
        expected_hash = hashlib.sha256((self.TX + self.ROOT).encode()).hexdigest()
        assert receipt.proof_hash == expected_hash
        # client recebeu os bytes corretos
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["scope"] == "tenant"
        assert int.from_bytes(call["scope_id"], "big") == 42
        assert call["merkle_root"] == bytes.fromhex(self.ROOT)
        assert call["period_start"] == 1700000000
        assert call["period_end"] == 1700086400

    def test_global_tem_scope_id_zero(self):
        client = _FakeClient()
        submit_to_polygon(
            self.ROOT, scope="global",
            period_start=1, period_end=2, client=client,
        )
        assert client.calls[0]["scope_id"] == b"\x00" * 32

    def test_root_invalido(self):
        with pytest.raises(PolygonError, match="64 chars"):
            submit_to_polygon(
                "abc", scope="global",
                period_start=1, period_end=2, client=_FakeClient(),
            )

    def test_periodo_invertido(self):
        with pytest.raises(PolygonError, match="period_end"):
            submit_to_polygon(
                self.ROOT, scope="global",
                period_start=10, period_end=1, client=_FakeClient(),
            )

    def test_client_erro_vira_submission_error(self):
        client = _FakeClient(raise_exc=RuntimeError("rpc down"))
        with pytest.raises(PolygonSubmissionError, match="Falha"):
            submit_to_polygon(
                self.ROOT, scope="global",
                period_start=1, period_end=2, client=client,
            )

    def test_tx_hash_nao_hex_rejeitado(self):
        client = _FakeClient(tx_hash="nao-e-hex")
        with pytest.raises(PolygonSubmissionError, match="tx_hash"):
            submit_to_polygon(
                self.ROOT, scope="global",
                period_start=1, period_end=2, client=client,
            )

    def test_sem_client_tenta_load_real(self, monkeypatch):
        def _no_pkg():
            raise PolygonUnavailableError("web3 ausente")
        monkeypatch.setattr(
            "src.integrations.polygon_anchor._load_real_client", _no_pkg
        )
        with pytest.raises(PolygonUnavailableError):
            submit_to_polygon(
                self.ROOT, scope="global",
                period_start=1, period_end=2,
            )

    def test_proof_uri_respeita_env_network(self, monkeypatch):
        monkeypatch.setenv("POLYGON_NETWORK", "mainnet")
        receipt = submit_to_polygon(
            self.ROOT, scope="global",
            period_start=1, period_end=2, client=_FakeClient(tx_hash=self.TX),
        )
        assert receipt.proof_uri == f"polygon://mainnet/tx/{self.TX}"


# ---------------------------------------------------------------------
# Dispatcher em anchoring_service
# ---------------------------------------------------------------------

class TestAnchoringDispatcherPolygon:
    ROOT = "a" * 64
    FROM_TS = 1700000000
    UNTIL_TS = 1700086400

    def test_provider_polygon_chama_wrapper(self, monkeypatch):
        from datetime import datetime, timezone
        fake_receipt = PolygonReceipt(
            transaction_id="0x" + "bc" * 32,
            proof_uri="polygon://amoy/tx/0xbc",
            proof_hash="d" * 64,
        )
        monkeypatch.setattr(
            "src.integrations.polygon_anchor.submit_to_polygon",
            lambda root, **kw: fake_receipt,
        )
        from src.services.anchoring_service import submit_anchor
        receipt = submit_anchor(
            self.ROOT, "polygon",
            provider="polygon",
            anchor_scope="tenant", tenant_id=42,
            covered_from=datetime.fromtimestamp(self.FROM_TS, tz=timezone.utc),
            covered_until=datetime.fromtimestamp(self.UNTIL_TS, tz=timezone.utc),
        )
        assert receipt.transaction_id == fake_receipt.transaction_id

    def test_polygon_sem_scope_rejeita(self, monkeypatch):
        from src.services.anchoring_service import AnchoringError, submit_anchor
        with pytest.raises(AnchoringError, match="anchor_scope"):
            submit_anchor(
                self.ROOT, "polygon", provider="polygon",
                anchor_scope=None, covered_from=None, covered_until=None,
            )

    def test_polygon_com_network_bitcoin_rejeitado(self, monkeypatch):
        from src.services.anchoring_service import AnchoringError, submit_anchor
        with pytest.raises(AnchoringError, match="network"):
            submit_anchor(
                self.ROOT, "bitcoin_ots", provider="polygon",
                anchor_scope="global",
            )

    def test_env_var_polygon(self, monkeypatch):
        from datetime import datetime, timezone
        monkeypatch.setenv("ANCHORING_PROVIDER", "polygon")
        fake_receipt = PolygonReceipt(
            transaction_id="0x" + "cd" * 32,
            proof_uri="polygon://amoy/tx/0xcd",
            proof_hash="e" * 64,
        )
        monkeypatch.setattr(
            "src.integrations.polygon_anchor.submit_to_polygon",
            lambda root, **kw: fake_receipt,
        )
        from src.services.anchoring_service import submit_anchor
        receipt = submit_anchor(
            self.ROOT, "polygon",
            anchor_scope="global",
            covered_from=datetime.fromtimestamp(self.FROM_TS, tz=timezone.utc),
            covered_until=datetime.fromtimestamp(self.UNTIL_TS, tz=timezone.utc),
        )
        assert receipt.transaction_id == fake_receipt.transaction_id


# ---------------------------------------------------------------------
# create_anchor end-to-end com provider=polygon
# ---------------------------------------------------------------------

class TestCreateAnchorPolygon:
    def test_create_anchor_roteia_para_polygon(self, monkeypatch):
        from datetime import datetime, timezone
        fake_receipt = PolygonReceipt(
            transaction_id="0x" + "de" * 32,
            proof_uri="polygon://amoy/tx/0xde",
            proof_hash="f" * 64,
        )
        monkeypatch.setattr(
            "src.integrations.polygon_anchor.submit_to_polygon",
            lambda root, **kw: fake_receipt,
        )

        # db fake
        from src.services import anchoring_service as anchor
        row = {
            "id": 1, "tenant_id": 1, "anchor_scope": "tenant",
            "events_count": 1, "merkle_root": "x" * 64,
            "blockchain_network": "polygon",
            "transaction_id": fake_receipt.transaction_id,
            "verification_status": "pending",
        }
        class _FC:
            def __init__(self, r): self._r = r
            def execute(self, *a, **kw): pass
            def fetchone(self): return self._r
        class _Conn:
            def commit(self): pass
        class _Ctx:
            def __enter__(self): return (_Conn(), _FC(row))
            def __exit__(self, *exc): return False
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _Ctx(),
        )

        events = [anchor.AnchorableEvent(
            event_table="traceability_events", event_id=1,
            event_hash="d" * 64,
            created_at=datetime.now(timezone.utc),
        )]
        result = anchor.create_anchor(
            tenant_id=1, anchor_scope="tenant",
            covered_from=datetime(2026, 4, 21, tzinfo=timezone.utc),
            covered_until=datetime(2026, 4, 22, tzinfo=timezone.utc),
            blockchain_network="polygon",
            events=events,
            provider="polygon",
        )
        assert result["transaction_id"] == fake_receipt.transaction_id


# ---------------------------------------------------------------------
# Contrato Solidity — smoke estatico
# ---------------------------------------------------------------------

class TestContractSource:
    def test_sandbox_anchor_tem_funcoes_esperadas(self):
        from pathlib import Path
        sol = Path("contracts/SandboxAnchor.sol").read_text(encoding="utf-8")
        assert "function anchor(" in sol
        assert "function anchorsCount(" in sol
        assert "function getAnchor(" in sol
        assert "function verifyRoot(" in sol
        assert "event Anchored(" in sol
        # valida scopes na mesma whitelist do service
        for scope in ("global", "tenant", "project"):
            assert f'keccak256("{scope}")' in sol

    def test_contrato_nao_tem_setter_nem_delete(self):
        from pathlib import Path
        sol = Path("contracts/SandboxAnchor.sol").read_text(encoding="utf-8")
        # No selfdestruct, transferOwnership, etc — append-only puro.
        forbidden = ("selfdestruct", "transferOwnership", "onlyOwner")
        for token in forbidden:
            assert token not in sol, token
