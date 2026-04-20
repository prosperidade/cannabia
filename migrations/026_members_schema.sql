-- Migration 026: Members Schema (F1.3 do docs/BACKLOG_SCC.md)
--
-- Cria as duas tabelas do dominio `members` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 5.1 e 5.2:
--
--   5.1  association_members   — vinculo formal pessoa ↔ associacao
--   5.2  member_consents       — historico de consentimentos do associado
--
-- Ordem de criacao respeita a unica FK interna desta migration:
--   member_consents.member_id -> association_members.id
-- Por isso `association_members` e criada ANTES de `member_consents`.
--
-- Dependencias externas (criadas em migrations anteriores):
--   - tenants(id)        — evoluida em 024_tenants_evolution
--   - patients(id)       — foundation
--   - prescriptions(id)  — criada em 012_prescriptions_orders
--
-- Decisao de namespace: schema `public` (mesma do 025, doc 25 §3 permite).
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. association_members  (doc 25 §5.1)
--
-- O UNIQUE (tenant_id, membership_number) permite que numeros de associado
-- se repitam entre tenants distintos — cada associacao tem seu proprio
-- esquema de numeracao.
--
-- `patient_id` e opcional porque nem todo associado tem cadastro clinico
-- (ex.: responsavel legal que nao recebe prescricao). Da mesma forma,
-- `prescription_on_file_id` e opcional — um associado pode estar pending
-- ou active sem prescricao vinculada ainda.
--
-- CHECK adicional (alem do doc) em `terminated_at >= joined_at`: impede
-- inconsistencia temporal (desligamento antes da entrada). Nao custa nada
-- e protege contra bug na camada de servico.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS association_members (
    id                      SERIAL PRIMARY KEY,
    tenant_id               INT NOT NULL REFERENCES tenants(id),
    patient_id              INT REFERENCES patients(id),
    membership_number       VARCHAR(64) NOT NULL,
    membership_status       VARCHAR(32) NOT NULL,
    joined_at               DATE NOT NULL,
    terminated_at           DATE,
    prescription_on_file_id INT REFERENCES prescriptions(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_members_tenant_number UNIQUE (tenant_id, membership_number),
    CONSTRAINT chk_members_status CHECK (
        membership_status IN ('pending', 'active', 'suspended', 'terminated')
    ),
    CONSTRAINT chk_members_termination_order CHECK (
        terminated_at IS NULL OR terminated_at >= joined_at
    )
);

CREATE INDEX IF NOT EXISTS idx_members_tenant
    ON association_members (tenant_id);
CREATE INDEX IF NOT EXISTS idx_members_patient
    ON association_members (patient_id);
CREATE INDEX IF NOT EXISTS idx_members_status
    ON association_members (membership_status);


-- ---------------------------------------------------------------------------
-- 2. member_consents  (doc 25 §5.2)
--
-- Historico append-only de consentimentos (LGPD + regulatorio). Nao ha
-- UPDATE conceitual — revogacao e feita setando `revoked_at`. Cada versao
-- de consentimento vira uma nova linha; o estado "vigente" de um tipo de
-- consentimento e a linha mais recente sem revoked_at.
--
-- `evidence_uri` e `evidence_hash` sao opcionais porque o consentimento
-- pode ser registrado por formulario eletronico (sem anexo) ou por
-- assinatura em papel digitalizado (com anexo + hash SHA-256).
--
-- CHECK em `revoked_at >= granted_at`: revogacao nao pode preceder a
-- concessao. Defensivo, alem do doc.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS member_consents (
    id              SERIAL PRIMARY KEY,
    member_id       INT NOT NULL REFERENCES association_members(id),
    consent_type    VARCHAR(64) NOT NULL,
    consent_version VARCHAR(32) NOT NULL,
    granted_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    evidence_uri    TEXT,
    evidence_hash   CHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_consents_revocation_order CHECK (
        revoked_at IS NULL OR revoked_at >= granted_at
    )
);

CREATE INDEX IF NOT EXISTS idx_consents_member
    ON member_consents (member_id);
CREATE INDEX IF NOT EXISTS idx_consents_type
    ON member_consents (consent_type);


-- ============================================================================
-- Fim da migration 026. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
