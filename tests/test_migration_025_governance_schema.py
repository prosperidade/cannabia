"""
Static validation of migration 025 (Governance Schema — F1.2 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as quatro tabelas previstas no doc 25 §§4.2-4.5 com as colunas,
   tipos e constraints exatas.
2. Respeita a ordem de criacao (institutional_documents antes de
   associations por causa da FK interna).
3. Usa IF NOT EXISTS em CREATE TABLE e CREATE INDEX (idempotencia).
4. Respeita FKs externas para tenants(id) e users(id).
5. Nao toca tabelas fora do escopo de F1.2.
6. Tem down-script paralelo com ordem reversa de DROP.

Validacao comportamental contra Postgres real fica para o passo de
roundtrip manual executado via scripts/run_migrations.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_025 = MIGRATIONS_DIR / "025_governance_schema.sql"
MIGRATION_025_DOWN = MIGRATIONS_DIR / "down" / "025_governance_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_025() -> str:
    assert MIGRATION_025.exists(), f"migration ausente: {MIGRATION_025}"
    content = _read(MIGRATION_025)
    assert content.strip(), "migration 025 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_025_down() -> str:
    assert MIGRATION_025_DOWN.exists(), f"down script ausente: {MIGRATION_025_DOWN}"
    content = _read(MIGRATION_025_DOWN)
    assert content.strip(), "down 025 esta vazio"
    return content


# ---------------------------------------------------------------------------
# Structure & rastreabilidade
# ---------------------------------------------------------------------------

class TestMigration025Structure:
    def test_has_header(self, sql_025: str) -> None:
        assert "Migration 025" in sql_025
        assert "Governance Schema" in sql_025

    def test_references_scc_sources(self, sql_025: str) -> None:
        assert "F1.2" in sql_025
        assert "BACKLOG_SCC" in sql_025 or "doc 25" in sql_025 or "25_SCC_DATA_MODEL" in sql_025

    def test_references_doc25_sections(self, sql_025: str) -> None:
        # As quatro subsecoes canonicas devem estar citadas no header/corpo.
        for section in ("§4.2", "§4.3", "§4.4", "§4.5"):
            assert section in sql_025, f"falta referencia a {section}"

    def test_no_manual_schema_migrations_insert(self, sql_025: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_025
        assert "UPDATE schema_migrations" not in sql_025


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration025Tables:
    @pytest.mark.parametrize(
        "table",
        [
            "institutional_documents",
            "technical_responsibles",
            "associations",
            "technical_operational_capacity",
        ],
    )
    def test_creates_table(self, sql_025: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_025

    def test_creates_exactly_four_tables(self, sql_025: str) -> None:
        # Garantia dupla: nao sobra CREATE TABLE orfao e nao faltam.
        # Filtra linhas de comentario para nao contar mencoes em prosa
        # no cabecalho da migration.
        code_lines = [
            line for line in sql_025.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE TABLE IF NOT EXISTS") == 4
        assert code.count("CREATE TABLE ") == code.count("CREATE TABLE IF NOT EXISTS")


# ---------------------------------------------------------------------------
# institutional_documents (doc 25 §4.4)
# ---------------------------------------------------------------------------

class TestInstitutionalDocuments:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id             SERIAL PRIMARY KEY",
            "tenant_id      INT NOT NULL REFERENCES tenants(id)",
            "document_type  VARCHAR(64) NOT NULL",
            "title          VARCHAR(255) NOT NULL",
            "version        VARCHAR(32) NOT NULL",
            "file_uri       TEXT NOT NULL",
            "file_hash      CHAR(64) NOT NULL",
            "valid_from     DATE NOT NULL",
            "valid_until    DATE",
            "is_active      BOOLEAN NOT NULL DEFAULT TRUE",
            "uploaded_by    INT REFERENCES users(id)",
            "created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ],
    )
    def test_has_column(self, sql_025: str, column_decl: str) -> None:
        assert column_decl in sql_025

    def test_indexes(self, sql_025: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_inst_docs_tenant" in sql_025
        assert "CREATE INDEX IF NOT EXISTS idx_inst_docs_type" in sql_025


# ---------------------------------------------------------------------------
# technical_responsibles (doc 25 §4.3)
# ---------------------------------------------------------------------------

class TestTechnicalResponsibles:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id                       SERIAL PRIMARY KEY",
            "tenant_id                INT NOT NULL REFERENCES tenants(id)",
            "user_id                  INT REFERENCES users(id)",
            "full_name                VARCHAR(255) NOT NULL",
            "professional_council     VARCHAR(32) NOT NULL",
            "council_number           VARCHAR(32) NOT NULL",
            "council_state            VARCHAR(2) NOT NULL",
            "habilitation_valid_until DATE",
            "document_ids             INT[] DEFAULT '{}'",
            "is_active                BOOLEAN NOT NULL DEFAULT TRUE",
        ],
    )
    def test_has_column(self, sql_025: str, column_decl: str) -> None:
        assert column_decl in sql_025

    def test_unique_council_triple(self, sql_025: str) -> None:
        # doc 25 §4.3: UNIQUE (professional_council, council_number, council_state).
        # Implementado como constraint nomeado para permitir drop explicito.
        assert (
            "CONSTRAINT uq_tr_council UNIQUE "
            "(professional_council, council_number, council_state)"
            in sql_025
        )

    def test_indexes(self, sql_025: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_tr_tenant" in sql_025
        assert "CREATE INDEX IF NOT EXISTS idx_tr_active" in sql_025


# ---------------------------------------------------------------------------
# associations (doc 25 §4.2)
# ---------------------------------------------------------------------------

class TestAssociations:
    def test_pk_is_tenant_id(self, sql_025: str) -> None:
        # Relacao 1:1 com tenants — tenant_id e PK e FK ao mesmo tempo.
        assert "tenant_id                  INT PRIMARY KEY REFERENCES tenants(id)" in sql_025

    def test_statute_document_fk(self, sql_025: str) -> None:
        # FK interna da migration: aponta para institutional_documents criada logo acima.
        assert (
            "statute_document_id        INT REFERENCES institutional_documents(id)"
            in sql_025
        )

    @pytest.mark.parametrize(
        "column_decl",
        [
            "directive_board            JSONB NOT NULL DEFAULT '[]'::jsonb",
            "members_count              INT NOT NULL DEFAULT 0",
            "is_judicial_operation      BOOLEAN NOT NULL DEFAULT FALSE",
            "judicial_authorization     TEXT",
            "sandbox_application_status VARCHAR(32)",
            "eligibility_validated_at   TIMESTAMPTZ",
        ],
    )
    def test_has_column(self, sql_025: str, column_decl: str) -> None:
        assert column_decl in sql_025

    def test_sandbox_status_check(self, sql_025: str) -> None:
        # CHECK nomeado, permite NULL + whitelist do doc 25 §4.2.
        assert "CONSTRAINT chk_assoc_sandbox_status CHECK" in sql_025
        assert "sandbox_application_status IS NULL" in sql_025
        for status in (
            "'not_started'",
            "'preparing'",
            "'submitted'",
            "'approved'",
            "'active'",
            "'concluded'",
            "'discontinued'",
        ):
            assert status in sql_025, f"falta status canonico: {status}"

    def test_members_count_non_negative(self, sql_025: str) -> None:
        # Defensivo: members_count >= 0. CHECK proprio para rastreabilidade do bug
        # se algum dia o servico tentar decrementar abaixo de zero.
        assert "CONSTRAINT chk_assoc_members_count CHECK (members_count >= 0)" in sql_025


# ---------------------------------------------------------------------------
# technical_operational_capacity (doc 25 §4.5)
# ---------------------------------------------------------------------------

class TestTechnicalOperationalCapacity:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id                     SERIAL PRIMARY KEY",
            "tenant_id              INT NOT NULL REFERENCES tenants(id)",
            "assessment_date        DATE NOT NULL",
            "infrastructure_score   JSONB NOT NULL",
            "human_resources_score  JSONB NOT NULL",
            "process_maturity_score JSONB NOT NULL",
            "proposed_scale         JSONB NOT NULL",
            "overall_readiness      NUMERIC(5,2)",
            "assessed_by            INT REFERENCES users(id)",
            "created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ],
    )
    def test_has_column(self, sql_025: str, column_decl: str) -> None:
        assert column_decl in sql_025

    def test_readiness_bounded_check(self, sql_025: str) -> None:
        # overall_readiness e opcional, mas quando presente deve estar em [0, 100]
        # (interpretacao semantica de NUMERIC(5,2) como percentual).
        assert "CONSTRAINT chk_toc_readiness CHECK" in sql_025
        assert "overall_readiness IS NULL" in sql_025
        assert "overall_readiness >= 0 AND overall_readiness <= 100" in sql_025


# ---------------------------------------------------------------------------
# Ordem de criacao (FK interna)
# ---------------------------------------------------------------------------

class TestMigration025CreationOrder:
    def test_institutional_documents_before_associations(self, sql_025: str) -> None:
        # associations.statute_document_id -> institutional_documents.id
        pos_inst_docs = sql_025.find("CREATE TABLE IF NOT EXISTS institutional_documents")
        pos_assoc = sql_025.find("CREATE TABLE IF NOT EXISTS associations")
        assert 0 < pos_inst_docs < pos_assoc, (
            "institutional_documents deve ser criada ANTES de associations "
            "(FK interna statute_document_id)"
        )


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration025Idempotency:
    def test_all_create_table_use_if_not_exists(self, sql_025: str) -> None:
        code_lines = [
            line for line in sql_025.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        total = code.count("CREATE TABLE")
        idempotent = code.count("CREATE TABLE IF NOT EXISTS")
        assert total == idempotent, (
            f"CREATE TABLE sem IF NOT EXISTS detectado: "
            f"{total - idempotent} ocorrencia(s) nao-idempotente(s)"
        )

    def test_all_indexes_use_if_not_exists(self, sql_025: str) -> None:
        code_lines = [
            line for line in sql_025.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE INDEX") == code.count("CREATE INDEX IF NOT EXISTS")


# ---------------------------------------------------------------------------
# Escopo — F1.2 nao pode invadir outras fases
# ---------------------------------------------------------------------------

class TestMigration025Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            "association_members",     # F2 (members schema, migration 026)
            "member_consents",         # F2
            "sops",                    # F3 (quality schema, 027)
            "sop_versions",            # F3
            "traceability_events",     # F4 (traceability, 028+)
            "adverse_events",          # F5 (pharmacovigilance, 031)
            "sandbox_projects",        # F6 (regulatory, 032)
            "blockchain_anchors",      # F7 (crypto, 033)
        ],
    )
    def test_does_not_create_out_of_scope_tables(
        self, sql_025: str, out_of_scope_table: str
    ) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_025
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_025

    def test_does_not_touch_tenants_table(self, sql_025: str) -> None:
        # F1.2 e novas tabelas. Evolucao de tenants ficou em F1.1/024.
        assert "ALTER TABLE tenants" not in sql_025
        assert "DROP TABLE" not in sql_025


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration025Down:
    def test_has_header(self, sql_025_down: str) -> None:
        assert "Down migration 025" in sql_025_down
        assert "Governance Schema" in sql_025_down

    @pytest.mark.parametrize(
        "table",
        [
            "associations",
            "technical_operational_capacity",
            "technical_responsibles",
            "institutional_documents",
        ],
    )
    def test_drops_every_created_table(self, sql_025_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_025_down

    def test_reverse_order_associations_before_institutional_documents(
        self, sql_025_down: str
    ) -> None:
        # FK interna: associations.statute_document_id -> institutional_documents.id
        # No DROP, associations precisa sair ANTES de institutional_documents.
        pos_assoc = sql_025_down.find("DROP TABLE IF EXISTS associations")
        pos_inst = sql_025_down.find("DROP TABLE IF EXISTS institutional_documents")
        assert 0 < pos_assoc < pos_inst, (
            "associations deve ser dropada ANTES de institutional_documents "
            "(FK interna statute_document_id)"
        )

    def test_all_drops_use_if_exists(self, sql_025_down: str) -> None:
        code_lines = [
            line for line in sql_025_down.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting_tables(self, sql_025_down: str) -> None:
        # users, tenants e tenant_types existiam antes da 025. Down nao pode
        # dropar esses — senao um rollback reverso quebraria o repo inteiro.
        for preexisting in ("users", "tenants", "tenant_types", "clinics"):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_025_down
            assert f"DROP TABLE {preexisting}" not in sql_025_down
