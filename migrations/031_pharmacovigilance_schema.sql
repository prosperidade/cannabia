-- Migration 031: Pharmacovigilance Schema (F3.1 do docs/BACKLOG_SCC.md)
--
-- Cria as 4 tabelas do dominio `pharmacovigilance` previstas no
-- docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md secoes 8.1 a 8.3:
--
--   8.1  adverse_events                    — eventos adversos reportados
--   8.2  pharmacovigilance_notifications   — notificacoes a orgaos (Vigimed, NotiVisa)
--   8.3  sanitary_risks + risk_controls    — matriz de riscos e controles
--
-- Ordem de criacao respeita FKs internas:
--   adverse_events     → pharmacovigilance_notifications
--   sanitary_risks     → risk_controls
--
-- Dependencias externas (ja criadas):
--   - tenants(id)             — 024
--   - users(id)               — foundation
--   - association_members(id) — 026
--   - preparations(id)        — 028
--   - sops(id)                — 027
--
-- Idempotencia: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- 1. adverse_events  (doc 25 §8.1)
--
-- `member_id` e `preparation_id` sao NULLABLE porque o evento pode ser
-- reportado por canal publico (ex.: WhatsApp de um usuario nao associado)
-- ou antes da dispensacao ser identificada.
--
-- CHECK defensivo alem do doc: event_onset_at <= reported_at. Onset e o
-- inicio do evento adverso, sempre anterior ou igual ao report.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS adverse_events (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    member_id           INT REFERENCES association_members(id),
    preparation_id      INT REFERENCES preparations(id),
    reported_at         TIMESTAMPTZ NOT NULL,
    event_onset_at      TIMESTAMPTZ,
    severity            VARCHAR(16) NOT NULL,
    description         TEXT NOT NULL,
    reported_via        VARCHAR(32) NOT NULL,
    ai_triage_result    JSONB,
    triaged_by          INT REFERENCES users(id),
    clinical_assessment TEXT,
    outcome             VARCHAR(32),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_ae_severity CHECK (
        severity IN ('mild', 'moderate', 'severe', 'life_threatening', 'fatal')
    ),
    CONSTRAINT chk_ae_reported_via CHECK (
        reported_via IN ('whatsapp', 'web', 'consultation', 'phone', 'other')
    ),
    CONSTRAINT chk_ae_outcome CHECK (
        outcome IS NULL
        OR outcome IN ('resolved', 'resolving', 'ongoing', 'worsened', 'unknown')
    ),
    CONSTRAINT chk_ae_onset_order CHECK (
        event_onset_at IS NULL OR event_onset_at <= reported_at
    )
);

CREATE INDEX IF NOT EXISTS idx_ae_tenant ON adverse_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_ae_member ON adverse_events (member_id);
CREATE INDEX IF NOT EXISTS idx_ae_severity ON adverse_events (severity);


-- ---------------------------------------------------------------------------
-- 2. pharmacovigilance_notifications  (doc 25 §8.2)
--
-- Cada evento adverso pode gerar multiplas notificacoes (Vigimed + NotiVisa
-- em casos graves). `response_payload` guarda JSONB com a resposta crua do
-- orgao regulador quando disponivel.
--
-- CHECK defensivo: response_received_at >= notified_at.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pharmacovigilance_notifications (
    id                     SERIAL PRIMARY KEY,
    adverse_event_id       INT NOT NULL REFERENCES adverse_events(id),
    notification_target    VARCHAR(32) NOT NULL,
    notified_at            TIMESTAMPTZ NOT NULL,
    notification_reference VARCHAR(255),
    response_received_at   TIMESTAMPTZ,
    response_payload       JSONB,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_pv_notif_target CHECK (
        notification_target IN ('vigimed', 'notivisa', 'internal_only')
    ),
    CONSTRAINT chk_pv_notif_response_order CHECK (
        response_received_at IS NULL OR response_received_at >= notified_at
    )
);

CREATE INDEX IF NOT EXISTS idx_pv_notif_ae ON pharmacovigilance_notifications (adverse_event_id);


-- ---------------------------------------------------------------------------
-- 3. sanitary_risks  (doc 25 §8.3)
--
-- Matriz de riscos sanitarios por tenant. `probability` e `impact` usam a
-- mesma whitelist de 5 niveis; `risk_level` e derivado (4 niveis) — doc nao
-- exige derivacao automatica, fica a cargo da aplicacao.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sanitary_risks (
    id          SERIAL PRIMARY KEY,
    tenant_id   INT NOT NULL REFERENCES tenants(id),
    risk_code   VARCHAR(64) NOT NULL,
    category    VARCHAR(64) NOT NULL,
    description TEXT NOT NULL,
    probability VARCHAR(16) NOT NULL,
    impact      VARCHAR(16) NOT NULL,
    risk_level  VARCHAR(16) NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sanitary_risks_tenant_code UNIQUE (tenant_id, risk_code),
    CONSTRAINT chk_sanitary_risks_probability CHECK (
        probability IN ('very_low', 'low', 'medium', 'high', 'very_high')
    ),
    CONSTRAINT chk_sanitary_risks_impact CHECK (
        impact IN ('very_low', 'low', 'medium', 'high', 'very_high')
    ),
    CONSTRAINT chk_sanitary_risks_level CHECK (
        risk_level IN ('low', 'medium', 'high', 'critical')
    )
);

CREATE INDEX IF NOT EXISTS idx_sanitary_risks_tenant ON sanitary_risks (tenant_id);
CREATE INDEX IF NOT EXISTS idx_sanitary_risks_level ON sanitary_risks (risk_level);


-- ---------------------------------------------------------------------------
-- 4. risk_controls  (doc 25 §8.3)
--
-- Cada risco pode ter multiplos controles. `related_sop_id` opcional porque
-- nem todo controle esta formalizado em um SOP (ex.: controle organizacional
-- por delegacao de autoridade).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_controls (
    id                  SERIAL PRIMARY KEY,
    risk_id             INT NOT NULL REFERENCES sanitary_risks(id),
    control_description TEXT NOT NULL,
    control_type        VARCHAR(32) NOT NULL,
    responsible         INT REFERENCES users(id),
    related_sop_id      INT REFERENCES sops(id),
    last_verified_at    TIMESTAMPTZ,
    verification_status VARCHAR(32),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_risk_controls_type CHECK (
        control_type IN ('preventive', 'detective', 'corrective', 'compensating')
    ),
    CONSTRAINT chk_risk_controls_verification CHECK (
        verification_status IS NULL
        OR verification_status IN ('effective', 'partial', 'ineffective', 'pending')
    )
);

CREATE INDEX IF NOT EXISTS idx_risk_controls_risk ON risk_controls (risk_id);
CREATE INDEX IF NOT EXISTS idx_risk_controls_sop ON risk_controls (related_sop_id);


-- ============================================================================
-- Fim da migration 031.
-- ============================================================================
