"""Testes do anchoring_service (F5.2 do SCC).

Tres camadas:

1. Merkle puro — sem DB, testa propriedades matematicas da arvore
   (raiz estavel, prova reconstrutivel, adulteracao detectada).
2. Submissao mock — determinismo e validacao de entradas.
3. Pipeline ``create_anchor`` — mocka db_cursor e injeta ``events``
   para testar persistencia sem depender de Postgres real.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import pytest

from src.services import anchoring_service as anchor
from src.services.anchoring_service import (
    AnchorableEvent,
    AnchoringError,
    MerkleProofStep,
    MockAnchorReceipt,
    NoEventsToAnchor,
    _pair_hash,
    build_merkle_proof,
    build_merkle_root,
    collect_anchorable_events,
    create_anchor,
    sha256_hex,
    submit_anchor_mock,
    verify_merkle_proof,
)


# Hashes "hex-looking" de 64 chars. So propriedade importa nos testes
# puros; nao precisam ser SHA-256 de nada real.
def _mk_leaf(seed: int) -> str:
    return hashlib.sha256(f"leaf-{seed}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# 1. Core Merkle
# ---------------------------------------------------------------------

class TestSha256:
    def test_hex_tem_64_chars(self):
        assert len(sha256_hex(b"qualquer")) == 64

    def test_hex_e_minusculo(self):
        assert sha256_hex(b"x").islower()


class TestMerkleRoot:
    def test_uma_folha_raiz_e_ela_mesma(self):
        leaf = _mk_leaf(0)
        assert build_merkle_root([leaf]) == leaf

    def test_duas_folhas_e_hash_da_concatenacao(self):
        a, b = _mk_leaf(0), _mk_leaf(1)
        esperado = _pair_hash(a, b)
        assert build_merkle_root([a, b]) == esperado

    def test_quatro_folhas_e_balanceada(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        l01 = _pair_hash(leaves[0], leaves[1])
        l23 = _pair_hash(leaves[2], leaves[3])
        esperado = _pair_hash(l01, l23)
        assert build_merkle_root(leaves) == esperado

    def test_tres_folhas_duplica_ultima(self):
        leaves = [_mk_leaf(i) for i in range(3)]
        # convencao Bitcoin: folha impar e auto-pareada
        l01 = _pair_hash(leaves[0], leaves[1])
        l22 = _pair_hash(leaves[2], leaves[2])
        esperado = _pair_hash(l01, l22)
        assert build_merkle_root(leaves) == esperado

    def test_cinco_folhas_auto_pares_em_multiplos_niveis(self):
        # leva a auto-pareamento no nivel 0 (5 folhas) e nivel 1 (3 nos).
        leaves = [_mk_leaf(i) for i in range(5)]
        # Apenas checa reprodutibilidade + shape — algebra exata nao
        # adiciona valor frente aos casos menores.
        r1 = build_merkle_root(leaves)
        r2 = build_merkle_root(list(leaves))
        assert r1 == r2
        assert len(r1) == 64

    def test_lista_vazia_erro(self):
        with pytest.raises(AnchoringError):
            build_merkle_root([])


class TestMerkleProof:
    def test_prova_vazia_para_uma_folha(self):
        leaf = _mk_leaf(0)
        assert build_merkle_proof([leaf], 0) == []

    def test_prova_reconstroi_raiz_duas_folhas(self):
        leaves = [_mk_leaf(0), _mk_leaf(1)]
        root = build_merkle_root(leaves)
        for idx in range(2):
            proof = build_merkle_proof(leaves, idx)
            assert verify_merkle_proof(leaves[idx], proof, root) is True

    def test_prova_reconstroi_raiz_quatro_folhas(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        root = build_merkle_root(leaves)
        for idx in range(4):
            proof = build_merkle_proof(leaves, idx)
            assert verify_merkle_proof(leaves[idx], proof, root) is True

    def test_prova_reconstroi_raiz_com_folha_impar(self):
        leaves = [_mk_leaf(i) for i in range(5)]
        root = build_merkle_root(leaves)
        for idx in range(5):
            proof = build_merkle_proof(leaves, idx)
            assert verify_merkle_proof(leaves[idx], proof, root) is True, idx

    def test_prova_serializa_para_json(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        proof = build_merkle_proof(leaves, 1)
        as_dicts = [step.to_dict() for step in proof]
        assert all(set(d.keys()) == {"hash", "side"} for d in as_dicts)
        assert all(d["side"] in {"left", "right"} for d in as_dicts)
        # reconstrucao a partir dos dicts funciona
        root = build_merkle_root(leaves)
        assert verify_merkle_proof(leaves[1], as_dicts, root)

    def test_adulteracao_do_leaf_falha(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        root = build_merkle_root(leaves)
        proof = build_merkle_proof(leaves, 0)
        tampered_leaf = _mk_leaf(99)
        assert verify_merkle_proof(tampered_leaf, proof, root) is False

    def test_adulteracao_da_prova_falha(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        root = build_merkle_root(leaves)
        proof = build_merkle_proof(leaves, 0)
        tampered = [
            MerkleProofStep(sibling_hash=_mk_leaf(77), side=step.side)
            for step in proof
        ]
        assert verify_merkle_proof(leaves[0], tampered, root) is False

    def test_adulteracao_da_raiz_falha(self):
        leaves = [_mk_leaf(i) for i in range(4)]
        proof = build_merkle_proof(leaves, 0)
        fake_root = _mk_leaf(999)
        assert verify_merkle_proof(leaves[0], proof, fake_root) is False

    def test_index_fora_do_range(self):
        leaves = [_mk_leaf(i) for i in range(3)]
        with pytest.raises(AnchoringError):
            build_merkle_proof(leaves, 3)
        with pytest.raises(AnchoringError):
            build_merkle_proof(leaves, -1)

    def test_side_invalido_na_verificacao(self):
        with pytest.raises(AnchoringError):
            verify_merkle_proof(
                _mk_leaf(0),
                [{"hash": _mk_leaf(1), "side": "diagonal"}],
                "x" * 64,
            )


# ---------------------------------------------------------------------
# 2. Submissao mock
# ---------------------------------------------------------------------

class TestSubmitMock:
    ROOT = "a" * 64

    def test_receipt_tem_tres_campos(self):
        r = submit_anchor_mock(self.ROOT, "bitcoin_ots", now_epoch=1700000000)
        assert isinstance(r, MockAnchorReceipt)
        assert r.transaction_id.startswith("mock:bitcoin_ots:")
        assert r.proof_uri.startswith("mock://bitcoin_ots/anchors/")
        assert len(r.proof_hash) == 64

    def test_transaction_id_inclui_prefixo_do_root_e_epoch(self):
        r = submit_anchor_mock(self.ROOT, "polygon", now_epoch=42)
        parts = r.transaction_id.split(":")
        assert parts == ["mock", "polygon", "a" * 16, "42"]

    def test_determinismo(self):
        r1 = submit_anchor_mock(self.ROOT, "ethereum", now_epoch=123)
        r2 = submit_anchor_mock(self.ROOT, "ethereum", now_epoch=123)
        assert r1 == r2

    def test_rede_invalida(self):
        with pytest.raises(AnchoringError, match="invalido"):
            submit_anchor_mock(self.ROOT, "solana")

    def test_root_com_tamanho_errado(self):
        with pytest.raises(AnchoringError, match="64 chars"):
            submit_anchor_mock("abc", "bitcoin_ots")


# ---------------------------------------------------------------------
# 3. Pipeline create_anchor — com db mockado
# ---------------------------------------------------------------------

class _FakeCursor:
    """Fake cursor que captura execute() e retorna um row pre-programado."""

    def __init__(self, insert_anchor_row: dict[str, Any]):
        self._next_row = insert_anchor_row
        self.executes: list[tuple[str, tuple]] = []

    def execute(self, sql: str, params: tuple = ()):
        self.executes.append((sql, tuple(params)))

    def fetchone(self):
        return self._next_row


class _FakeConn:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class _FakeDbCtx:
    def __init__(self, insert_anchor_row):
        self.conn = _FakeConn()
        self.cursor = _FakeCursor(insert_anchor_row)

    def __enter__(self):
        return (self.conn, self.cursor)

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_db(monkeypatch):
    """Instala um db_cursor fake e retorna o ctx construido."""
    def _install(anchor_row: dict[str, Any]) -> _FakeDbCtx:
        ctx = _FakeDbCtx(anchor_row)
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: ctx,
        )
        return ctx

    return _install


def _sample_events(n: int) -> list[AnchorableEvent]:
    base = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    return [
        AnchorableEvent(
            event_table="traceability_events",
            event_id=100 + i,
            event_hash=_mk_leaf(i),
            created_at=base,
        )
        for i in range(n)
    ]


class TestCreateAnchorPipeline:
    FROM = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)
    UNTIL = datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc)

    def _anchor_row(self, anchor_id: int = 1) -> dict[str, Any]:
        return {
            "id": anchor_id,
            "tenant_id": 1,
            "anchor_scope": "tenant",
            "covered_from": self.FROM,
            "covered_until": self.UNTIL,
            "events_count": 4,
            "merkle_root": "x" * 64,
            "blockchain_network": "bitcoin_ots",
            "transaction_id": "mock:bitcoin_ots:xxxx:1",
            "verification_status": "pending",
        }

    def test_happy_path_insere_anchor_e_mappings(self, fake_db):
        ctx = fake_db(self._anchor_row(42))
        events = _sample_events(4)
        result = create_anchor(
            tenant_id=1,
            anchor_scope="tenant",
            covered_from=self.FROM,
            covered_until=self.UNTIL,
            events=events,
            now_epoch=1700000000,
        )
        # 1 INSERT em blockchain_anchors + 4 INSERTs em anchor_event_mappings
        assert len(ctx.cursor.executes) == 5
        assert "INSERT INTO blockchain_anchors" in ctx.cursor.executes[0][0]
        for stmt, params in ctx.cursor.executes[1:]:
            assert "anchor_event_mappings" in stmt
            assert params[0] == 42  # anchor_id
        assert ctx.conn.commits == 1
        assert result["id"] == 42
        assert result["events"] == events
        assert len(result["merkle_root"]) == 64

    def test_merkle_root_retornado_bate_com_folhas(self, fake_db):
        fake_db(self._anchor_row())
        events = _sample_events(3)
        result = create_anchor(
            tenant_id=1,
            anchor_scope="tenant",
            covered_from=self.FROM,
            covered_until=self.UNTIL,
            events=events,
        )
        expected = build_merkle_root([e.event_hash for e in events])
        assert result["merkle_root"] == expected

    def test_merkle_path_persistido_e_valido(self, fake_db):
        ctx = fake_db(self._anchor_row())
        events = _sample_events(4)
        create_anchor(
            tenant_id=1,
            anchor_scope="tenant",
            covered_from=self.FROM,
            covered_until=self.UNTIL,
            events=events,
        )
        root = build_merkle_root([e.event_hash for e in events])
        # Para cada INSERT em mapping, decodifica merkle_path JSONB e
        # verifica prova.
        mapping_execs = ctx.cursor.executes[1:]
        for event, (_, params) in zip(events, mapping_execs):
            _anchor_id, table, event_id, event_hash, path_json = params
            assert table == event.event_table
            assert event_id == event.event_id
            assert event_hash == event.event_hash
            path = json.loads(path_json)
            assert verify_merkle_proof(event.event_hash, path, root) is True

    def test_scope_global_nao_aceita_tenant_id(self, fake_db):
        fake_db(self._anchor_row())
        with pytest.raises(AnchoringError, match="global"):
            create_anchor(
                tenant_id=1,
                anchor_scope="global",
                covered_from=self.FROM,
                covered_until=self.UNTIL,
                events=_sample_events(2),
            )

    def test_scope_tenant_exige_tenant_id(self, fake_db):
        fake_db(self._anchor_row())
        with pytest.raises(AnchoringError, match="exige tenant_id"):
            create_anchor(
                tenant_id=None,
                anchor_scope="tenant",
                covered_from=self.FROM,
                covered_until=self.UNTIL,
                events=_sample_events(2),
            )

    def test_scope_invalido(self, fake_db):
        with pytest.raises(AnchoringError, match="anchor_scope"):
            create_anchor(
                tenant_id=1,
                anchor_scope="warehouse",
                covered_from=self.FROM,
                covered_until=self.UNTIL,
                events=_sample_events(1),
            )

    def test_sem_eventos_eleva_NoEventsToAnchor(self, fake_db):
        with pytest.raises(NoEventsToAnchor):
            create_anchor(
                tenant_id=1,
                anchor_scope="tenant",
                covered_from=self.FROM,
                covered_until=self.UNTIL,
                events=[],
            )

    def test_janela_invertida(self, fake_db):
        with pytest.raises(AnchoringError, match="covered_until"):
            create_anchor(
                tenant_id=1,
                anchor_scope="tenant",
                covered_from=self.UNTIL,
                covered_until=self.FROM,
                events=_sample_events(1),
            )

    def test_network_invalida(self, fake_db):
        with pytest.raises(AnchoringError, match="blockchain_network"):
            create_anchor(
                tenant_id=1,
                anchor_scope="tenant",
                covered_from=self.FROM,
                covered_until=self.UNTIL,
                blockchain_network="solana",
                events=_sample_events(1),
            )


# ---------------------------------------------------------------------
# 4. collect_anchorable_events — mock do db_cursor
# ---------------------------------------------------------------------

class _MultiQueryCursor:
    """Fake cursor que programa uma resposta por chamada de execute()."""

    def __init__(self, responses: list[list[dict]]):
        self._responses = list(responses)
        self._last: list[dict] = []
        self.executes: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.executes.append((sql, tuple(params)))
        self._last = self._responses.pop(0) if self._responses else []

    def fetchall(self):
        return list(self._last)


class _MultiCtx:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return (None, self.cursor)

    def __exit__(self, *exc):
        return False


class TestCollectEvents:
    FROM = datetime(2026, 4, 20, tzinfo=timezone.utc)
    UNTIL = datetime(2026, 4, 21, tzinfo=timezone.utc)

    def test_agrega_de_todas_as_tabelas_e_ordena(self, monkeypatch):
        # uma linha por tabela, para ver se todas sao tocadas
        responses = [
            [{"pk": 1, "hash": _mk_leaf(1),
              "created_at": datetime(2026, 4, 20, 10, tzinfo=timezone.utc)}],
            [{"pk": 2, "hash": _mk_leaf(2),
              "created_at": datetime(2026, 4, 20, 8, tzinfo=timezone.utc)}],
            [{"pk": 3, "hash": _mk_leaf(3),
              "created_at": datetime(2026, 4, 20, 9, tzinfo=timezone.utc)}],
            [{"pk": 4, "hash": _mk_leaf(4),
              "created_at": datetime(2026, 4, 20, 11, tzinfo=timezone.utc)}],
        ]
        cursor = _MultiQueryCursor(responses)
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _MultiCtx(cursor),
        )

        events = collect_anchorable_events(
            tenant_id=1,
            covered_from=self.FROM,
            covered_until=self.UNTIL,
        )
        assert len(events) == 4
        # uma query por tabela em EVENT_TABLES
        assert len(cursor.executes) == len(anchor.EVENT_TABLES)
        # resultado ordenado por created_at ASC
        timestamps = [e.created_at for e in events]
        assert timestamps == sorted(timestamps)

    def test_global_scope_nao_filtra_por_tenant(self, monkeypatch):
        cursor = _MultiQueryCursor([[] for _ in anchor.EVENT_TABLES])
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _MultiCtx(cursor),
        )
        collect_anchorable_events(
            tenant_id=None,
            covered_from=self.FROM,
            covered_until=self.UNTIL,
        )
        for sql, params in cursor.executes:
            assert "tenant_id" not in sql
            # so dois params: covered_from, covered_until
            assert len(params) == 2

    def test_tenant_scope_filtra_por_tenant(self, monkeypatch):
        cursor = _MultiQueryCursor([[] for _ in anchor.EVENT_TABLES])
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _MultiCtx(cursor),
        )
        collect_anchorable_events(
            tenant_id=7,
            covered_from=self.FROM,
            covered_until=self.UNTIL,
        )
        for sql, params in cursor.executes:
            assert "tenant_id = %s" in sql
            assert params[2] == 7

    def test_lab_analyses_tem_filtro_report_hash_not_null(self, monkeypatch):
        cursor = _MultiQueryCursor([[] for _ in anchor.EVENT_TABLES])
        monkeypatch.setattr(
            "src.services.anchoring_service.db_cursor",
            lambda dictionary=True: _MultiCtx(cursor),
        )
        collect_anchorable_events(
            tenant_id=1,
            covered_from=self.FROM,
            covered_until=self.UNTIL,
        )
        lab_stmts = [s for s, _ in cursor.executes if "FROM lab_analyses" in s]
        assert lab_stmts, "lab_analyses deve aparecer na coleta"
        assert "report_hash IS NOT NULL" in lab_stmts[0]

    def test_janela_invertida_erro(self):
        with pytest.raises(AnchoringError, match="invertida"):
            collect_anchorable_events(
                tenant_id=1,
                covered_from=self.UNTIL,
                covered_until=self.FROM,
            )
