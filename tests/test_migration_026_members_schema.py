"""
Static validation of migration 026 (Members Schema — F1.3 do SCC).

Valida por inspecao estatica do SQL que a migration:

1. Cria as duas tabelas previstas no doc 25 §§5.1-5.2 com as colunas,
   tipos e constraints exatas.
2. Respeita a ordem de criacao (association_members antes de
   member_consents por causa da FK interna).
3. Usa IF NOT EXISTS em CREATE TABLE e CREATE INDEX (idempotencia).
4. Respeita FKs externas para tenants(id), patients(id), prescriptions(id).
5. Nao toca tabelas fora do escopo de F1.3.
6. Tem down-script paralelo com ordem reversa de DROP.

Validacao comportamental contra Postgres real fica para o passo de
roundtrip manual executado via scripts/run_migrations.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
MIGRATION_026 = MIGRATIONS_DIR / "026_members_schema.sql"
MIGRATION_026_DOWN = MIGRATIONS_DIR / "down" / "026_members_schema_down.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sql_026() -> str:
    assert MIGRATION_026.exists(), f"migration ausente: {MIGRATION_026}"
    content = _read(MIGRATION_026)
    assert content.strip(), "migration 026 esta vazia"
    return content


@pytest.fixture(scope="module")
def sql_026_down() -> str:
    assert MIGRATION_026_DOWN.exists(), f"down script ausente: {MIGRATION_026_DOWN}"
    content = _read(MIGRATION_026_DOWN)
    assert content.strip(), "down 026 esta vazio"
    return content


# ---------------------------------------------------------------------------
# Structure & rastreabilidade
# ---------------------------------------------------------------------------

class TestMigration026Structure:
    def test_has_header(self, sql_026: str) -> None:
        assert "Migration 026" in sql_026
        assert "Members Schema" in sql_026

    def test_references_scc_sources(self, sql_026: str) -> None:
        assert "F1.3" in sql_026
        assert "BACKLOG_SCC" in sql_026 or "doc 25" in sql_026 or "25_SCC_DATA_MODEL" in sql_026

    def test_references_doc25_sections(self, sql_026: str) -> None:
        for section in ("§5.1", "§5.2"):
            assert section in sql_026, f"falta referencia a {section}"

    def test_no_manual_schema_migrations_insert(self, sql_026: str) -> None:
        assert "INSERT INTO schema_migrations" not in sql_026
        assert "UPDATE schema_migrations" not in sql_026


# ---------------------------------------------------------------------------
# Tabelas criadas
# ---------------------------------------------------------------------------

class TestMigration026Tables:
    @pytest.mark.parametrize(
        "table",
        ["association_members", "member_consents"],
    )
    def test_creates_table(self, sql_026: str, table: str) -> None:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql_026

    def test_creates_exactly_two_tables(self, sql_026: str) -> None:
        code_lines = [
            line for line in sql_026.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE TABLE IF NOT EXISTS") == 2
        assert code.count("CREATE TABLE ") == code.count("CREATE TABLE IF NOT EXISTS")


# ---------------------------------------------------------------------------
# association_members (doc 25 §5.1)
# ---------------------------------------------------------------------------

class TestAssociationMembers:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id                      SERIAL PRIMARY KEY",
            "tenant_id               INT NOT NULL REFERENCES tenants(id)",
            "patient_id              INT REFERENCES patients(id)",
            "membership_number       VARCHAR(64) NOT NULL",
            "membership_status       VARCHAR(32) NOT NULL",
            "joined_at               DATE NOT NULL",
            "terminated_at           DATE",
            "prescription_on_file_id INT REFERENCES prescriptions(id)",
            "created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()",
            "updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ],
    )
    def test_has_column(self, sql_026: str, column_decl: str) -> None:
        assert column_decl in sql_026

    def test_unique_tenant_number(self, sql_026: str) -> None:
        # doc 25 §5.1: UNIQUE (tenant_id, membership_number) permite
        # numeracao propria por tenant.
        assert (
            "CONSTRAINT uq_members_tenant_number UNIQUE (tenant_id, membership_number)"
            in sql_026
        )

    def test_status_check_whitelist(self, sql_026: str) -> None:
        assert "CONSTRAINT chk_members_status CHECK" in sql_026
        for status in ("'pending'", "'active'", "'suspended'", "'terminated'"):
            assert status in sql_026, f"falta status canonico: {status}"

    def test_termination_order_check(self, sql_026: str) -> None:
        # Defensivo alem do doc: terminated_at nao pode ser anterior a joined_at.
        assert "CONSTRAINT chk_members_termination_order CHECK" in sql_026
        assert "terminated_at IS NULL OR terminated_at >= joined_at" in sql_026

    def test_indexes(self, sql_026: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_members_tenant" in sql_026
        assert "CREATE INDEX IF NOT EXISTS idx_members_patient" in sql_026
        assert "CREATE INDEX IF NOT EXISTS idx_members_status" in sql_026


# ---------------------------------------------------------------------------
# member_consents (doc 25 §5.2)
# ---------------------------------------------------------------------------

class TestMemberConsents:
    @pytest.mark.parametrize(
        "column_decl",
        [
            "id              SERIAL PRIMARY KEY",
            "member_id       INT NOT NULL REFERENCES association_members(id)",
            "consent_type    VARCHAR(64) NOT NULL",
            "consent_version VARCHAR(32) NOT NULL",
            "granted_at      TIMESTAMPTZ NOT NULL",
            "revoked_at      TIMESTAMPTZ",
            "evidence_uri    TEXT",
            "evidence_hash   CHAR(64)",
            "created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        ],
    )
    def test_has_column(self, sql_026: str, column_decl: str) -> None:
        assert column_decl in sql_026

    def test_revocation_order_check(self, sql_026: str) -> None:
        # Defensivo alem do doc: revoked_at nao pode preceder granted_at.
        assert "CONSTRAINT chk_consents_revocation_order CHECK" in sql_026
        assert "revoked_at IS NULL OR revoked_at >= granted_at" in sql_026

    def test_indexes(self, sql_026: str) -> None:
        assert "CREATE INDEX IF NOT EXISTS idx_consents_member" in sql_026
        assert "CREATE INDEX IF NOT EXISTS idx_consents_type" in sql_026


# ---------------------------------------------------------------------------
# Ordem de criacao (FK interna)
# ---------------------------------------------------------------------------

class TestMigration026CreationOrder:
    def test_association_members_before_member_consents(self, sql_026: str) -> None:
        # member_consents.member_id -> association_members.id
        pos_members = sql_026.find("CREATE TABLE IF NOT EXISTS association_members")
        pos_consents = sql_026.find("CREATE TABLE IF NOT EXISTS member_consents")
        assert 0 < pos_members < pos_consents, (
            "association_members deve ser criada ANTES de member_consents "
            "(FK interna member_id)"
        )


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

class TestMigration026Idempotency:
    def test_all_create_table_use_if_not_exists(self, sql_026: str) -> None:
        code_lines = [
            line for line in sql_026.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        total = code.count("CREATE TABLE")
        idempotent = code.count("CREATE TABLE IF NOT EXISTS")
        assert total == idempotent

    def test_all_indexes_use_if_not_exists(self, sql_026: str) -> None:
        code_lines = [
            line for line in sql_026.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("CREATE INDEX") == code.count("CREATE INDEX IF NOT EXISTS")


# ---------------------------------------------------------------------------
# Escopo — F1.3 nao pode invadir outras fases
# ---------------------------------------------------------------------------

class TestMigration026Scope:
    @pytest.mark.parametrize(
        "out_of_scope_table",
        [
            # F1.2 (ja criadas pela 025)
            "institutional_documents",
            "technical_responsibles",
            "associations",
            "technical_operational_capacity",
            # F3+ (futuras)
            "sops",
            "sop_versions",
            "traceability_events",
            "adverse_events",
            "sandbox_projects",
            "blockchain_anchors",
        ],
    )
    def test_does_not_recreate_out_of_scope_tables(
        self, sql_026: str, out_of_scope_table: str
    ) -> None:
        assert f"CREATE TABLE {out_of_scope_table}" not in sql_026
        assert f"CREATE TABLE IF NOT EXISTS {out_of_scope_table}" not in sql_026

    def test_does_not_touch_tenants_or_patients(self, sql_026: str) -> None:
        # F1.3 cria novas tabelas; nao evolui tenants/patients/prescriptions.
        assert "ALTER TABLE tenants" not in sql_026
        assert "ALTER TABLE patients" not in sql_026
        assert "ALTER TABLE prescriptions" not in sql_026
        assert "DROP TABLE" not in sql_026


# ---------------------------------------------------------------------------
# Down script
# ---------------------------------------------------------------------------

class TestMigration026Down:
    def test_has_header(self, sql_026_down: str) -> None:
        assert "Down migration 026" in sql_026_down
        assert "Members Schema" in sql_026_down

    @pytest.mark.parametrize(
        "table",
        ["association_members", "member_consents"],
    )
    def test_drops_every_created_table(self, sql_026_down: str, table: str) -> None:
        assert f"DROP TABLE IF EXISTS {table}" in sql_026_down

    def test_reverse_order_consents_before_members(self, sql_026_down: str) -> None:
        # FK interna: member_consents.member_id -> association_members.id
        # No DROP, consents precisa sair ANTES de association_members.
        pos_consents = sql_026_down.find("DROP TABLE IF EXISTS member_consents")
        pos_members = sql_026_down.find("DROP TABLE IF EXISTS association_members")
        assert 0 < pos_consents < pos_members, (
            "member_consents deve ser dropada ANTES de association_members "
            "(FK interna member_id)"
        )

    def test_all_drops_use_if_exists(self, sql_026_down: str) -> None:
        code_lines = [
            line for line in sql_026_down.splitlines()
            if not line.lstrip().startswith("--")
        ]
        code = "\n".join(code_lines)
        assert code.count("DROP TABLE") == code.count("DROP TABLE IF EXISTS")

    def test_does_not_touch_preexisting_tables(self, sql_026_down: str) -> None:
        for preexisting in (
            "tenants", "patients", "prescriptions",
            "institutional_documents", "technical_responsibles", "associations",
        ):
            assert f"DROP TABLE IF EXISTS {preexisting}" not in sql_026_down
            assert f"DROP TABLE {preexisting}" not in sql_026_down
