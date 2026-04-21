"""Testes do endpoint publico de verificacao de ancoragem (F5.5 do SCC).

Usa Flask test client + monkeypatch do repository para nao depender de
Postgres real. O foco aqui e o contrato do endpoint publico:

- parsing/validacao dos parametros,
- filtro por escopo (tenant vs global),
- executar ``verify_merkle_proof`` server-side e expor ``server_verified``,
- codigos de status e formato da resposta.

A matematica da Merkle tree ja e coberta por test_anchoring_service.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from src.services.anchoring_service import (
    build_merkle_proof,
    build_merkle_root,
)


def _leaf(seed: int) -> str:
    return hashlib.sha256(f"evt-{seed}".encode("utf-8")).hexdigest()


@pytest.fixture
def tree_and_proof():
    """Gera uma arvore valida de 4 folhas + prova do indice 0."""
    leaves = [_leaf(i) for i in range(4)]
    root = build_merkle_root(leaves)
    proof_steps = build_merkle_proof(leaves, 0)
    merkle_path = [step.to_dict() for step in proof_steps]
    return {
        "leaves": leaves,
        "root": root,
        "merkle_path": merkle_path,
    }


def _make_mapping(
    *,
    tree_and_proof: dict,
    anchor_id: int = 42,
    tenant_id: int | None = 1,
    anchor_scope: str = "tenant",
    override_hash: str | None = None,
    override_path=None,
) -> dict:
    base_date = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    return {
        "anchor_id": anchor_id,
        "event_table": "traceability_events",
        "event_id": 123,
        "event_hash": override_hash or tree_and_proof["leaves"][0],
        "merkle_path": override_path if override_path is not None else tree_and_proof["merkle_path"],
        "tenant_id": tenant_id,
        "anchor_scope": anchor_scope,
        "merkle_root": tree_and_proof["root"],
        "transaction_id": "mock:bitcoin_ots:abcdef0123456789:1700000000",
        "blockchain_network": "bitcoin_ots",
        "verification_status": "pending",
        "anchored_at": base_date,
        "verified_at": None,
        "covered_from": datetime(2026, 4, 20, tzinfo=timezone.utc),
        "covered_until": datetime(2026, 4, 21, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------

class TestVerifyHappyPath:
    def test_retorna_ancoragem_e_server_verified_true(
        self, client, monkeypatch, tree_and_proof
    ):
        mapping = _make_mapping(tree_and_proof=tree_and_proof)
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping],
        )

        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["request"] == {
            "tenant_id": 1,
            "event_table": "traceability_events",
            "event_id": 123,
        }
        assert len(body["anchors"]) == 1
        anchor = body["anchors"][0]
        assert anchor["anchor_id"] == 42
        assert anchor["server_verified"] is True
        assert anchor["transaction_id"].startswith("mock:bitcoin_ots:")
        assert len(anchor["merkle_root"]) == 64
        assert body["all_verified"] is True

    def test_scope_global_cobre_qualquer_tenant(
        self, client, monkeypatch, tree_and_proof
    ):
        mapping = _make_mapping(
            tree_and_proof=tree_and_proof,
            tenant_id=None,
            anchor_scope="global",
        )
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping],
        )
        # Pede tenant_id=99 (nao e o tenant 'dono' do evento), mas scope=global cobre
        resp = client.get(
            "/api/v1/public/anchors/99/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert len(body["anchors"]) == 1
        assert body["anchors"][0]["anchor_scope"] == "global"

    def test_filtra_anchors_de_outros_tenants(
        self, client, monkeypatch, tree_and_proof
    ):
        keep = _make_mapping(
            tree_and_proof=tree_and_proof, anchor_id=1, tenant_id=1
        )
        drop = _make_mapping(
            tree_and_proof=tree_and_proof, anchor_id=2, tenant_id=2
        )
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [keep, drop],
        )
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
        anchor_ids = [a["anchor_id"] for a in resp.get_json()["data"]["anchors"]]
        assert anchor_ids == [1]


# ---------------------------------------------------------------------
# server_verified negativo
# ---------------------------------------------------------------------

class TestServerVerifiedNegative:
    def test_event_hash_adulterado_marca_false(
        self, client, monkeypatch, tree_and_proof
    ):
        # leaf errado em relacao a prova original
        mapping = _make_mapping(
            tree_and_proof=tree_and_proof,
            override_hash=_leaf(999),
        )
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping],
        )
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["anchors"][0]["server_verified"] is False
        assert body["all_verified"] is False

    def test_merkle_path_malformado_marca_false(
        self, client, monkeypatch, tree_and_proof
    ):
        mapping = _make_mapping(
            tree_and_proof=tree_and_proof,
            override_path=[{"hash": "x" * 64, "side": "top"}],  # side invalido
        )
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping],
        )
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["anchors"][0]["server_verified"] is False


# ---------------------------------------------------------------------
# Validacao de parametros
# ---------------------------------------------------------------------

class TestParameterValidation:
    def test_event_id_ausente(self, client):
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "missing_event_id"

    def test_event_id_nao_numerico(self, client):
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": "abc"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "invalid_event_id"

    def test_table_ausente(self, client):
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"event_id": 123},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "missing_table"

    def test_table_fora_da_whitelist(self, client):
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "users", "event_id": 1},
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_table"

    def test_tenant_id_nao_inteiro_retorna_404_do_flask(self, client):
        # <int:tenant_id> → Flask retorna 404 se nao converte
        resp = client.get(
            "/api/v1/public/anchors/abc/verify",
            query_string={"table": "traceability_events", "event_id": 1},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------
# 404 quando nao ha mapping
# ---------------------------------------------------------------------

class TestNotFound:
    def test_sem_mapping_retorna_404(self, client, monkeypatch):
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [],
        )
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 999},
        )
        assert resp.status_code == 404
        err = resp.get_json()["error"]
        assert err["code"] == "anchor_not_found"
        assert err["details"]["event_id"] == 999

    def test_so_tem_mapping_de_outro_tenant_retorna_404(
        self, client, monkeypatch, tree_and_proof
    ):
        mapping_other = _make_mapping(
            tree_and_proof=tree_and_proof, tenant_id=99
        )
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping_other],
        )
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------
# Endpoint e realmente publico (sem auth/csrf)
# ---------------------------------------------------------------------

class TestPublicAccess:
    def test_sem_sessao_ou_cookie_funciona(
        self, client, monkeypatch, tree_and_proof
    ):
        """Sanity check: sem qualquer sessao/cookie, o endpoint responde 200."""
        mapping = _make_mapping(tree_and_proof=tree_and_proof)
        monkeypatch.setattr(
            "src.web.routes.public_anchors.get_mappings_for_event",
            lambda table, event_id: [mapping],
        )
        # client e fresh a cada teste; nao ha _user_id nas cookies
        resp = client.get(
            "/api/v1/public/anchors/1/verify",
            query_string={"table": "traceability_events", "event_id": 123},
        )
        assert resp.status_code == 200
