"""Integration tests do anchoring_service + endpoint publico (F5.6 do SCC).

Exercita o pipeline completo de ancoragem contra o Postgres real:

    seed eventos → create_anchor → persistencia real em blockchain_anchors
    + anchor_event_mappings → leitura via get_mappings_for_event →
    verificacao via GET /api/v1/public/anchors/<tenant>/verify

Os testes unitarios em test_anchoring_service.py usam db_cursor mockado;
aqui exercitamos as mesmas funcoes contra a DB real para pegar:

  - erros de SQL que escapam aos mocks (tipo CHAR(64) vs VARCHAR, JSONB
    cast mal feito, ordem de colunas errada no INSERT)
  - CHECK constraints da migration 033 (coverage_order, events_count,
    scope/network/verification whitelist)
  - PK composta bloqueando mapping duplicado
  - comportamento do tenant_id nullable com scope='global'

Skipif no modulo inteiro — CI sem docker-compose do banco nao quebra.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Iterator

import pytest

from src.infra.database import db_cursor
from src.services.anchoring_service import (
    AnchorableEvent,
    NoEventsToAnchor,
    build_merkle_proof,
    build_merkle_root,
    collect_anchorable_events,
    create_anchor,
    get_anchor,
    get_mappings_for_event,
    verify_merkle_proof,
)


def _db_reachable() -> bool:
    try:
        with db_cursor() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="Postgres de integracao indisponivel — suba cannabia-postgis",
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture
def tenant_id() -> Iterator[int]:
    """Cria um tenant descartavel e limpa no teardown incluindo
    quaisquer rows de blockchain_anchors / mappings / eventos seedados."""
    slug = f"test-anchor-{uuid.uuid4().hex[:8]}"

    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            "SELECT id FROM tenant_types WHERE slug = 'association' LIMIT 1"
        )
        tt = cursor.fetchone()
        if tt is None:
            cursor.execute(
                "INSERT INTO tenant_types (slug, display_name) "
                "VALUES ('association', 'Associacao') RETURNING id"
            )
            tt = cursor.fetchone()
        cursor.execute(
            """
            INSERT INTO tenants (
                legal_name, display_name, slug, status,
                tenant_type_id, tenant_type, plan_tier, incorporation_date
            )
            VALUES (%s, %s, %s, 'active', %s, 'association', 'basic', %s)
            RETURNING id
            """,
            (slug, slug, slug, tt["id"],
             date.today() - timedelta(days=365 * 3)),
        )
        tid = cursor.fetchone()["id"]
        conn.commit()

    try:
        yield tid
    finally:
        # traceability_events tem trigger append-only (migration 030) que
        # bloqueia DELETE em producao. Para limpeza de teste, desligamos
        # temporariamente as triggers nessa sessao (session-local, precisa
        # SUPERUSER ou REPLICATION — usuario da DB de dev tem isso).
        with db_cursor() as (conn, cursor):
            cursor.execute("SET LOCAL session_replication_role = 'replica'")
            # Mappings antes dos anchors (FK)
            cursor.execute(
                "DELETE FROM anchor_event_mappings "
                "WHERE anchor_id IN (SELECT id FROM blockchain_anchors WHERE tenant_id=%s)",
                (tid,),
            )
            cursor.execute(
                "DELETE FROM blockchain_anchors WHERE tenant_id=%s", (tid,)
            )
            # Eventos seedados
            cursor.execute("DELETE FROM traceability_events WHERE tenant_id=%s", (tid,))
            cursor.execute("DELETE FROM regulatory_submissions WHERE tenant_id=%s", (tid,))
            cursor.execute("DELETE FROM lab_analyses WHERE tenant_id=%s", (tid,))
            cursor.execute("DELETE FROM tenants WHERE id=%s", (tid,))
            conn.commit()


# ---------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------

def _hash_payload(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seed_traceability_events(
    tenant_id: int, n: int, base_hash: str = "evt"
) -> list[int]:
    """Seedam n eventos em traceability_events, cada um em chain_id
    proprio com chain_sequence=1 e previous_hash=NULL (trigger de
    continuidade so valida seq>=2)."""
    ids: list[int] = []
    with db_cursor(dictionary=True) as (conn, cursor):
        for i in range(n):
            ev_hash = _hash_payload(f"{base_hash}-{tenant_id}-{i}-{uuid.uuid4().hex}")
            cursor.execute(
                """
                INSERT INTO traceability_events (
                    tenant_id, event_type, subject_type, subject_id,
                    payload, chain_id, chain_sequence, event_hash,
                    previous_hash, occurred_at
                )
                VALUES (%s, 'test_event', 'harvest', %s,
                        %s::jsonb, %s, 1, %s, NULL, NOW())
                RETURNING id
                """,
                (
                    tenant_id,
                    1000 + i,
                    '{"test": true}',
                    f"chain-{uuid.uuid4().hex[:12]}",
                    ev_hash,
                ),
            )
            ids.append(cursor.fetchone()["id"])
        conn.commit()
    return ids


def _seed_regulatory_submission(tenant_id: int) -> int:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO regulatory_submissions (
                tenant_id, submission_type, submitted_at,
                payload_uri, payload_hash
            )
            VALUES (%s, 'periodic_report', NOW(), %s, %s)
            RETURNING id
            """,
            (
                tenant_id,
                f"s3://test/{uuid.uuid4().hex}.pdf",
                _hash_payload(f"reg-{tenant_id}-{uuid.uuid4().hex}"),
            ),
        )
        sid = cursor.fetchone()["id"]
        conn.commit()
    return sid


def _seed_lab_analysis(tenant_id: int, *, with_hash: bool = True) -> int:
    with db_cursor(dictionary=True) as (conn, cursor):
        cursor.execute(
            """
            INSERT INTO lab_analyses (
                tenant_id, subject_type, subject_id, lab_name,
                report_number, analysis_date, cannabinoid_profile,
                conformity_status, report_hash
            )
            VALUES (%s, 'harvest', %s, 'LabTest', %s, %s,
                    '{"thc": 0.3}'::jsonb, 'conforming', %s)
            RETURNING id
            """,
            (
                tenant_id,
                5000,
                f"rep-{uuid.uuid4().hex[:8]}",
                date.today(),
                _hash_payload(f"lab-{tenant_id}-{uuid.uuid4().hex}") if with_hash else None,
            ),
        )
        lid = cursor.fetchone()["id"]
        conn.commit()
    return lid


# ---------------------------------------------------------------------
# Pipeline end-to-end
# ---------------------------------------------------------------------

class TestCreateAnchorE2E:
    def test_persiste_anchor_e_mappings(self, tenant_id):
        _seed_traceability_events(tenant_id, 3)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)

        result = create_anchor(
            tenant_id=tenant_id,
            anchor_scope="tenant",
            covered_from=from_,
            covered_until=until,
        )

        anchor = get_anchor(int(result["id"]))
        assert anchor["tenant_id"] == tenant_id
        assert anchor["anchor_scope"] == "tenant"
        assert anchor["events_count"] == 3
        assert len(anchor["merkle_root"]) == 64
        assert anchor["transaction_id"].startswith("mock:bitcoin_ots:")
        assert anchor["verification_status"] == "pending"

        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                "SELECT COUNT(*) AS n FROM anchor_event_mappings WHERE anchor_id=%s",
                (anchor["id"],),
            )
            assert cursor.fetchone()["n"] == 3

    def test_merkle_path_do_db_reconstroi_raiz(self, tenant_id):
        _seed_traceability_events(tenant_id, 4)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        result = create_anchor(
            tenant_id=tenant_id,
            anchor_scope="tenant",
            covered_from=from_,
            covered_until=until,
        )
        root = result["merkle_root"]

        with db_cursor(dictionary=True) as (_, cursor):
            cursor.execute(
                "SELECT event_hash, merkle_path FROM anchor_event_mappings "
                "WHERE anchor_id=%s",
                (result["id"],),
            )
            for row in cursor.fetchall():
                # psycopg2 decodifica JSONB em list/dict automaticamente
                assert verify_merkle_proof(
                    row["event_hash"], row["merkle_path"], root
                ) is True

    def test_scope_global_com_tenant_null(self, tenant_id):
        _seed_traceability_events(tenant_id, 2)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        # collect com tenant_id=None puxa eventos de todos tenants —
        # para isolar, injeta events explicitamente.
        events = [
            AnchorableEvent(
                event_table="traceability_events",
                event_id=i,
                event_hash=_hash_payload(f"glob-{i}"),
                created_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]
        result = create_anchor(
            tenant_id=None,
            anchor_scope="global",
            covered_from=from_,
            covered_until=until,
            events=events,
        )
        anchor = get_anchor(int(result["id"]))
        assert anchor["tenant_id"] is None
        assert anchor["anchor_scope"] == "global"

        # cleanup manual desta ancoragem global (sem tenant_id, fixture nao pega)
        with db_cursor() as (conn, cursor):
            cursor.execute(
                "DELETE FROM anchor_event_mappings WHERE anchor_id=%s",
                (anchor["id"],),
            )
            cursor.execute(
                "DELETE FROM blockchain_anchors WHERE id=%s", (anchor["id"],)
            )
            conn.commit()


# ---------------------------------------------------------------------
# Collect events real
# ---------------------------------------------------------------------

class TestCollectEventsReal:
    def test_coleta_de_multiplas_tabelas(self, tenant_id):
        _seed_traceability_events(tenant_id, 2)
        _seed_regulatory_submission(tenant_id)
        _seed_lab_analysis(tenant_id, with_hash=True)

        from_ = datetime.now(timezone.utc) - timedelta(hours=1)
        until = datetime.now(timezone.utc) + timedelta(hours=1)

        events = collect_anchorable_events(
            tenant_id=tenant_id,
            covered_from=from_,
            covered_until=until,
        )
        tables = {e.event_table for e in events}
        assert "traceability_events" in tables
        assert "regulatory_submissions" in tables
        assert "lab_analyses" in tables
        # 2 trace + 1 reg + 1 lab
        assert len(events) == 4

    def test_lab_analysis_sem_hash_e_ignorada(self, tenant_id):
        _seed_lab_analysis(tenant_id, with_hash=False)
        from_ = datetime.now(timezone.utc) - timedelta(hours=1)
        until = datetime.now(timezone.utc) + timedelta(hours=1)

        events = collect_anchorable_events(
            tenant_id=tenant_id,
            covered_from=from_,
            covered_until=until,
        )
        assert all(e.event_table != "lab_analyses" for e in events)

    def test_sem_eventos_no_periodo(self, tenant_id):
        from_ = datetime.now(timezone.utc) - timedelta(hours=2)
        until = datetime.now(timezone.utc) - timedelta(hours=1)
        with pytest.raises(NoEventsToAnchor):
            create_anchor(
                tenant_id=tenant_id,
                anchor_scope="tenant",
                covered_from=from_,
                covered_until=until,
            )


# ---------------------------------------------------------------------
# Read via get_mappings_for_event
# ---------------------------------------------------------------------

class TestGetMappingsForEvent:
    def test_retorna_anchor_do_evento(self, tenant_id):
        event_ids = _seed_traceability_events(tenant_id, 2)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        create_anchor(
            tenant_id=tenant_id,
            anchor_scope="tenant",
            covered_from=from_,
            covered_until=until,
        )

        mappings = get_mappings_for_event("traceability_events", event_ids[0])
        assert len(mappings) >= 1
        m = mappings[0]
        assert m["tenant_id"] == tenant_id
        assert m["anchor_scope"] == "tenant"
        assert m["event_id"] == event_ids[0]
        assert len(m["merkle_root"]) == 64
        # merkle_path veio como list de dicts (JSONB auto-decoded)
        assert isinstance(m["merkle_path"], list)


# ---------------------------------------------------------------------
# Constraints da migration 033
# ---------------------------------------------------------------------

class TestDbConstraints:
    def test_pk_composta_bloqueia_mapping_duplicado(self, tenant_id):
        _seed_traceability_events(tenant_id, 1)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        result = create_anchor(
            tenant_id=tenant_id,
            anchor_scope="tenant",
            covered_from=from_,
            covered_until=until,
        )
        anchor_id = int(result["id"])
        event = result["events"][0]

        from psycopg2 import IntegrityError
        with db_cursor() as (conn, cursor):
            try:
                cursor.execute(
                    """
                    INSERT INTO anchor_event_mappings
                        (anchor_id, event_table, event_id, event_hash, merkle_path)
                    VALUES (%s, %s, %s, %s, '[]'::jsonb)
                    """,
                    (anchor_id, event.event_table, event.event_id, event.event_hash),
                )
                conn.commit()
                pytest.fail("Esperava IntegrityError na PK composta")
            except IntegrityError:
                conn.rollback()

    def test_check_coverage_order_bloqueia_janela_invertida(self, tenant_id):
        from psycopg2 import IntegrityError
        now = datetime.now(timezone.utc)
        with db_cursor() as (conn, cursor):
            try:
                cursor.execute(
                    """
                    INSERT INTO blockchain_anchors (
                        tenant_id, anchor_scope, covered_from, covered_until,
                        events_count, merkle_root, blockchain_network,
                        transaction_id
                    )
                    VALUES (%s, 'tenant', %s, %s, 1, %s, 'bitcoin_ots', 'xxx')
                    """,
                    (tenant_id, now, now - timedelta(hours=1), "a" * 64),
                )
                conn.commit()
                pytest.fail("Esperava IntegrityError do CHECK coverage_order")
            except IntegrityError:
                conn.rollback()

    def test_check_network_bloqueia_rede_fora_whitelist(self, tenant_id):
        from psycopg2 import IntegrityError
        now = datetime.now(timezone.utc)
        with db_cursor() as (conn, cursor):
            try:
                cursor.execute(
                    """
                    INSERT INTO blockchain_anchors (
                        tenant_id, anchor_scope, covered_from, covered_until,
                        events_count, merkle_root, blockchain_network,
                        transaction_id
                    )
                    VALUES (%s, 'tenant', %s, %s, 1, %s, 'solana', 'xxx')
                    """,
                    (tenant_id, now - timedelta(hours=1), now, "a" * 64),
                )
                conn.commit()
                pytest.fail("Esperava IntegrityError do CHECK blockchain_network")
            except IntegrityError:
                conn.rollback()


# ---------------------------------------------------------------------
# Endpoint publico contra DB real
# ---------------------------------------------------------------------

class TestPublicAnchorEndpointE2E:
    def test_verify_retorna_anchor_persistido_com_server_verified_true(
        self, client, tenant_id
    ):
        event_ids = _seed_traceability_events(tenant_id, 3)
        from_ = datetime.now(timezone.utc) - timedelta(minutes=10)
        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        create_anchor(
            tenant_id=tenant_id,
            anchor_scope="tenant",
            covered_from=from_,
            covered_until=until,
        )

        resp = client.get(
            f"/api/v1/public/anchors/{tenant_id}/verify",
            query_string={
                "table": "traceability_events",
                "event_id": event_ids[0],
            },
        )
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["request"]["tenant_id"] == tenant_id
        assert body["request"]["event_id"] == event_ids[0]
        assert len(body["anchors"]) == 1
        anchor = body["anchors"][0]
        assert anchor["server_verified"] is True
        assert anchor["tenant_id"] == tenant_id
        assert anchor["anchor_scope"] == "tenant"
        assert anchor["blockchain_network"] == "bitcoin_ots"
        assert anchor["transaction_id"].startswith("mock:bitcoin_ots:")
        assert len(anchor["merkle_root"]) == 64

        # Sanity: verify cliente-side tambem bate
        assert verify_merkle_proof(
            anchor["event_hash"], anchor["merkle_path"], anchor["merkle_root"]
        ) is True
        assert body["all_verified"] is True

    def test_verify_404_quando_evento_nao_tem_anchor(self, client, tenant_id):
        resp = client.get(
            f"/api/v1/public/anchors/{tenant_id}/verify",
            query_string={
                "table": "traceability_events",
                "event_id": 9999999,
            },
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "anchor_not_found"
