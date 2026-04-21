"""Testes do wrapper OpenTimestamps (F5.3 do SCC).

O pacote ``opentimestamps-client`` do PyPI NAO e obrigatorio em CI — o
wrapper foi desenhado para ser testavel via client injetado. Os testes
aqui nao dependem do pacote estar instalado.
"""

from __future__ import annotations

import hashlib

import pytest

from src.integrations import opentimestamps as ots
from src.integrations.opentimestamps import (
    OtsError,
    OtsReceipt,
    OtsSubmissionError,
    OtsUnavailableError,
    submit_to_ots,
)


class _FakeClient:
    """Client fake que devolve bytes deterministas por hash do input."""

    def __init__(self, *, devolucao: bytes | None = None):
        self._devolucao = devolucao
        self.calls: list[bytes] = []

    def stamp(self, data: bytes) -> bytes:
        self.calls.append(data)
        if self._devolucao is not None:
            return self._devolucao
        # Default: envelope simulado com o hash duplo do input.
        return b"OTSMOCK:" + hashlib.sha256(data).digest()


class _BrokenClient:
    def stamp(self, data: bytes) -> bytes:
        raise RuntimeError("calendar offline")


class _NonBytesClient:
    def stamp(self, data: bytes):
        return "not bytes"


# ---------------------------------------------------------------------
# submit_to_ots
# ---------------------------------------------------------------------

class TestSubmitToOts:
    ROOT = "a" * 64

    def test_happy_path_com_client_injetado(self):
        client = _FakeClient()
        receipt = submit_to_ots(self.ROOT, client=client)
        assert isinstance(receipt, OtsReceipt)
        assert receipt.transaction_id == "ots:" + self.ROOT[:16]
        assert receipt.proof_uri == f"data/anchors/{self.ROOT}.ots"
        assert len(receipt.proof_hash) == 64
        # o client recebeu bytes de 32
        assert len(client.calls) == 1
        assert len(client.calls[0]) == 32

    def test_proof_hash_bate_com_sha256_dos_bytes_devolvidos(self):
        devolucao = b"fake-proof-bytes"
        client = _FakeClient(devolucao=devolucao)
        receipt = submit_to_ots(self.ROOT, client=client)
        assert receipt.proof_hash == hashlib.sha256(devolucao).hexdigest()

    def test_receipt_e_imutavel(self):
        receipt = submit_to_ots(self.ROOT, client=_FakeClient())
        with pytest.raises((AttributeError, TypeError)):
            receipt.transaction_id = "hackeado"

    def test_root_com_tamanho_errado_levanta(self):
        with pytest.raises(OtsError, match="64 chars"):
            submit_to_ots("abc", client=_FakeClient())

    def test_client_quebrado_levanta_submission_error(self):
        with pytest.raises(OtsSubmissionError, match="Falha"):
            submit_to_ots(self.ROOT, client=_BrokenClient())

    def test_client_que_retorna_nao_bytes_levanta(self):
        with pytest.raises(OtsSubmissionError, match="nao-bytes"):
            submit_to_ots(self.ROOT, client=_NonBytesClient())

    def test_sem_client_tenta_load_real(self, monkeypatch):
        """Se o pacote PyPI nao esta instalado, _load_real_client levanta
        OtsUnavailableError — testamos forcando esse caminho."""
        def _no_pkg():
            raise OtsUnavailableError(
                "Pacote 'opentimestamps-client' nao instalado."
            )
        monkeypatch.setattr(
            "src.integrations.opentimestamps._load_real_client", _no_pkg
        )
        with pytest.raises(OtsUnavailableError):
            submit_to_ots(self.ROOT)


# ---------------------------------------------------------------------
# Dispatcher em anchoring_service
# ---------------------------------------------------------------------

class TestAnchoringDispatcher:
    ROOT = "a" * 64

    def test_default_e_mock(self, monkeypatch):
        """Sem env var e sem provider explicito → mock."""
        monkeypatch.delenv("ANCHORING_PROVIDER", raising=False)
        from src.services.anchoring_service import submit_anchor
        receipt = submit_anchor(self.ROOT, "bitcoin_ots", now_epoch=1700000000)
        assert receipt.transaction_id.startswith("mock:bitcoin_ots:")

    def test_env_var_ots_usa_wrapper(self, monkeypatch):
        monkeypatch.setenv("ANCHORING_PROVIDER", "ots")
        # Mocka submit_to_ots para nao depender do pacote PyPI
        fake_receipt = OtsReceipt(
            transaction_id="ots:prefix",
            proof_uri="data/anchors/x.ots",
            proof_hash="b" * 64,
        )
        monkeypatch.setattr(
            "src.integrations.opentimestamps.submit_to_ots",
            lambda root: fake_receipt,
        )
        from src.services.anchoring_service import submit_anchor
        receipt = submit_anchor(self.ROOT, "bitcoin_ots")
        assert receipt.transaction_id == "ots:prefix"

    def test_provider_explicito_vence_env_var(self, monkeypatch):
        monkeypatch.setenv("ANCHORING_PROVIDER", "ots")
        from src.services.anchoring_service import submit_anchor
        # provider explicito 'mock' deve ignorar env
        receipt = submit_anchor(
            self.ROOT, "bitcoin_ots", provider="mock", now_epoch=42
        )
        assert receipt.transaction_id.startswith("mock:bitcoin_ots:")

    def test_ots_com_network_polygon_rejeitado(self, monkeypatch):
        from src.services.anchoring_service import (
            AnchoringError, submit_anchor,
        )
        monkeypatch.delenv("ANCHORING_PROVIDER", raising=False)
        with pytest.raises(AnchoringError, match="bitcoin_ots"):
            submit_anchor(self.ROOT, "polygon", provider="ots")

    def test_provider_invalido_rejeitado(self, monkeypatch):
        from src.services.anchoring_service import (
            AnchoringError, submit_anchor,
        )
        with pytest.raises(AnchoringError, match="invalido"):
            submit_anchor(self.ROOT, "bitcoin_ots", provider="solana")


# ---------------------------------------------------------------------
# create_anchor agora respeita env var
# ---------------------------------------------------------------------

class TestCreateAnchorUsesDispatcher:
    def test_create_anchor_com_provider_ots_chama_wrapper(self, monkeypatch):
        """create_anchor deve rotear pela cadeia submit_anchor → ots
        quando provider='ots'. Mocka submit_to_ots para nao depender
        do pacote PyPI; mocka db_cursor para nao depender de DB."""
        from datetime import datetime, timezone

        from src.services import anchoring_service as anchor

        fake_receipt = OtsReceipt(
            transaction_id="ots:abcdef0123456789",
            proof_uri="data/anchors/x.ots",
            proof_hash="c" * 64,
        )
        monkeypatch.setattr(
            "src.integrations.opentimestamps.submit_to_ots",
            lambda root: fake_receipt,
        )

        # db fake
        class _FC:
            def __init__(self, row):
                self._row = row
                self.execs = 0
            def execute(self, *a, **kw): self.execs += 1
            def fetchone(self): return self._row
        anchor_row = {
            "id": 1, "tenant_id": 1, "anchor_scope": "tenant",
            "events_count": 1,
            "merkle_root": "x" * 64, "blockchain_network": "bitcoin_ots",
            "transaction_id": fake_receipt.transaction_id,
            "verification_status": "pending",
        }
        class _Conn:
            def commit(self): pass
        class _Ctx:
            def __enter__(self):
                return (_Conn(), _FC(anchor_row))
            def __exit__(self, *exc): return False
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _Ctx(),
        )

        from src.services.anchoring_service import AnchorableEvent
        events = [AnchorableEvent(
            event_table="traceability_events",
            event_id=1,
            event_hash="d" * 64,
            created_at=datetime.now(timezone.utc),
        )]
        result = anchor.create_anchor(
            tenant_id=1, anchor_scope="tenant",
            covered_from=datetime(2026, 4, 21, tzinfo=timezone.utc),
            covered_until=datetime(2026, 4, 22, tzinfo=timezone.utc),
            blockchain_network="bitcoin_ots",
            events=events,
            provider="ots",
        )
        # transaction_id do mock OTS chegou ao row final
        assert result["transaction_id"] == fake_receipt.transaction_id
