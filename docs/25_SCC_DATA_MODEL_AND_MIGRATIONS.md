# 25 — Modelagem de Dados e Migrations do Sandbox Compliance Core

## 1. Propósito do documento

Este documento materializa a modelagem lógica da Seção 7 do `23_SANDBOX_COMPLIANCE_CORE.md` em **modelagem física aterrissável** no banco PostgreSQL da CannabIA.

Ele define:

- Schemas lógicos de cada domínio do SCC.
- Estrutura física das tabelas (colunas, tipos, constraints, índices).
- Convenções de append-only, hash chaining e proteção contra alteração retroativa.
- Estrutura das migrations e ordem sugerida de aplicação.
- Estratégia de evolução do modelo existente sem romper compatibilidade.

O objetivo é que este documento, combinado ao `22`, sirva de especificação suficiente para que o time de engenharia (humano ou assistido por IA) produza as migrations SQL finais e atualize os blueprints Flask correspondentes.

---

## 2. Princípios de modelagem

### 2.1. Compatibilidade com o existente

O SCC estende o modelo atual da CannabIA, que é centrado em `clinic_id`. A estratégia é:

- Introduzir a entidade `tenants` como discriminador genérico, mantendo `clinics` como visão especializada para retrocompatibilidade.
- Associações são um novo tipo de tenant.
- Médicos autônomos são um terceiro tipo de tenant.
- Pacientes existentes continuam vinculados ao tenant que os atende; ganham vínculo opcional a `association_members` quando o tenant for associação.

### 2.2. Separação de eventos e contexto

A fronteira arquitetural entre **evento imutável** e **contexto mutável** é estrutural:

- Tabelas de evento são **append-only**, sem PII sensível, com hash encadeado.
- Tabelas de contexto contêm PII, são mutáveis, apagáveis sob LGPD.
- Eventos referenciam contexto por ID, nunca por valor.

Isso garante que o direito de apagamento não quebre a cadeia de auditoria.

### 2.3. Hash chaining

Toda tabela de evento possui:

- `event_hash` — hash SHA-256 do conteúdo canônico do evento.
- `previous_hash` — hash do evento imediatamente anterior na mesma cadeia lógica.
- `chain_id` — identificador da cadeia à qual o evento pertence (ex.: lote, associação).
- `chain_sequence` — número sequencial do evento dentro da cadeia.

### 2.4. Protection triggers

Tabelas de evento e de auditoria possuem triggers de banco que:

- Impedem UPDATE e DELETE via constraint de role.
- Recalculam e validam o hash no INSERT.
- Verificam a continuidade da cadeia (o `previous_hash` fornecido corresponde ao último hash da cadeia).

### 2.5. Timestamps e autoria

Toda tabela carrega:

- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `created_by_user_id INT REFERENCES users(id)` quando aplicável.
- `tenant_id INT NOT NULL REFERENCES tenants(id)` exceto em tabelas globais.

### 2.6. Convenções de nomenclatura

- Tabelas em `snake_case`, plural.
- Colunas em `snake_case`.
- Chaves estrangeiras com sufixo `_id`.
- Timestamps com sufixo `_at`.
- Booleanos com prefixo `is_` ou `has_`.
- Enums via colunas `VARCHAR` com CHECK constraint explícito, evitando tipo ENUM nativo do PostgreSQL para facilitar migrations.

---

## 3. Schemas lógicos

O SCC é organizado em sete schemas lógicos, que podem ser implementados como schemas PostgreSQL distintos ou como prefixos de nome em um schema único, conforme decisão operacional do time.

| Schema lógico | Domínio |
|---|---|
| `governance` | Tenants, associações, responsáveis técnicos, documentos institucionais |
| `members` | Associados, vínculos, consentimentos |
| `quality` | SOPs, versões, treinamentos, evidências, desvios, CAPAs |
| `traceability` | Sementes, plantas, lotes, colheitas, extrações, preparados, dispensações, eventos, laudos |
| `pharmacovigilance` | Eventos adversos, notificações, riscos, controles |
| `regulatory` | Projetos experimentais, protocolos, indicadores, submissões, relatórios |
| `crypto` | Ancoragens em blockchain, provas, verificações |

---

## 4. Schema `governance`

### 4.1. `tenants`

Evolução de `clinics` como entidade genérica de tenant.

```sql
CREATE TABLE tenants (
    id                   SERIAL PRIMARY KEY,
    tenant_type          VARCHAR(32) NOT NULL
                         CHECK (tenant_type IN ('clinic', 'association', 'solo_doctor')),
    legal_name           VARCHAR(255) NOT NULL,
    trade_name           VARCHAR(255),
    cnpj                 VARCHAR(14) UNIQUE,
    incorporation_date   DATE,
    plan_tier            VARCHAR(32) NOT NULL
                         CHECK (plan_tier IN ('basic', 'pro', 'premium', 'sandbox_ready')),
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    whitelabel_config    JSONB,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_type ON tenants(tenant_type);
CREATE INDEX idx_tenants_plan_tier ON tenants(plan_tier);
```

### 4.2. `associations`

Extensão especializada para tenants do tipo `association`.

```sql
CREATE TABLE associations (
    tenant_id                INT PRIMARY KEY REFERENCES tenants(id),
    statute_document_id      INT REFERENCES institutional_documents(id),
    directive_board          JSONB NOT NULL DEFAULT '[]',
    members_count            INT NOT NULL DEFAULT 0,
    is_judicial_operation    BOOLEAN NOT NULL DEFAULT FALSE,
    judicial_authorization   TEXT,
    sandbox_application_status VARCHAR(32)
                             CHECK (sandbox_application_status IN
                             ('not_started', 'preparing', 'submitted', 'approved', 'active', 'concluded', 'discontinued')),
    eligibility_validated_at TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 4.3. `technical_responsibles`

```sql
CREATE TABLE technical_responsibles (
    id                 SERIAL PRIMARY KEY,
    tenant_id          INT NOT NULL REFERENCES tenants(id),
    user_id            INT REFERENCES users(id),
    full_name          VARCHAR(255) NOT NULL,
    professional_council VARCHAR(32) NOT NULL,
    council_number     VARCHAR(32) NOT NULL,
    council_state      VARCHAR(2) NOT NULL,
    habilitation_valid_until DATE,
    document_ids       INT[] DEFAULT '{}',
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (professional_council, council_number, council_state)
);

CREATE INDEX idx_tr_tenant ON technical_responsibles(tenant_id);
CREATE INDEX idx_tr_active ON technical_responsibles(is_active);
```

### 4.4. `institutional_documents`

```sql
CREATE TABLE institutional_documents (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    document_type   VARCHAR(64) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    version         VARCHAR(32) NOT NULL,
    file_uri        TEXT NOT NULL,
    file_hash       CHAR(64) NOT NULL,
    valid_from      DATE NOT NULL,
    valid_until     DATE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    uploaded_by     INT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inst_docs_tenant ON institutional_documents(tenant_id);
CREATE INDEX idx_inst_docs_type ON institutional_documents(document_type);
```

### 4.5. `technical_operational_capacity`

```sql
CREATE TABLE technical_operational_capacity (
    id                      SERIAL PRIMARY KEY,
    tenant_id               INT NOT NULL REFERENCES tenants(id),
    assessment_date         DATE NOT NULL,
    infrastructure_score    JSONB NOT NULL,
    human_resources_score   JSONB NOT NULL,
    process_maturity_score  JSONB NOT NULL,
    proposed_scale          JSONB NOT NULL,
    overall_readiness       NUMERIC(5,2),
    assessed_by             INT REFERENCES users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 5. Schema `members`

### 5.1. `association_members`

Vínculo formal entre pessoa (que pode estar também em `patients`) e associação.

```sql
CREATE TABLE association_members (
    id                    SERIAL PRIMARY KEY,
    tenant_id             INT NOT NULL REFERENCES tenants(id),
    patient_id            INT REFERENCES patients(id),
    membership_number     VARCHAR(64) NOT NULL,
    membership_status     VARCHAR(32) NOT NULL
                          CHECK (membership_status IN ('pending', 'active', 'suspended', 'terminated')),
    joined_at             DATE NOT NULL,
    terminated_at         DATE,
    prescription_on_file_id INT REFERENCES prescriptions(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, membership_number)
);

CREATE INDEX idx_members_tenant ON association_members(tenant_id);
CREATE INDEX idx_members_patient ON association_members(patient_id);
CREATE INDEX idx_members_status ON association_members(membership_status);
```

### 5.2. `member_consents`

```sql
CREATE TABLE member_consents (
    id                 SERIAL PRIMARY KEY,
    member_id          INT NOT NULL REFERENCES association_members(id),
    consent_type       VARCHAR(64) NOT NULL,
    consent_version    VARCHAR(32) NOT NULL,
    granted_at         TIMESTAMPTZ NOT NULL,
    revoked_at         TIMESTAMPTZ,
    evidence_uri       TEXT,
    evidence_hash      CHAR(64),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_member ON member_consents(member_id);
CREATE INDEX idx_consents_type ON member_consents(consent_type);
```

---

## 6. Schema `quality`

### 6.1. `sops` e `sop_versions`

```sql
CREATE TABLE sops (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    code            VARCHAR(64) NOT NULL,
    title           VARCHAR(255) NOT NULL,
    area            VARCHAR(64) NOT NULL,
    current_version_id INT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, code)
);

CREATE TABLE sop_versions (
    id              SERIAL PRIMARY KEY,
    sop_id          INT NOT NULL REFERENCES sops(id),
    version_number  VARCHAR(32) NOT NULL,
    content_uri     TEXT NOT NULL,
    content_hash    CHAR(64) NOT NULL,
    effective_from  DATE NOT NULL,
    effective_until DATE,
    approved_by     INT REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sop_id, version_number)
);

ALTER TABLE sops
    ADD CONSTRAINT fk_sops_current_version
    FOREIGN KEY (current_version_id) REFERENCES sop_versions(id);
```

### 6.2. `sop_trainings`

```sql
CREATE TABLE sop_trainings (
    id              SERIAL PRIMARY KEY,
    sop_version_id  INT NOT NULL REFERENCES sop_versions(id),
    user_id         INT NOT NULL REFERENCES users(id),
    trained_at      TIMESTAMPTZ NOT NULL,
    evidence_uri    TEXT,
    evidence_hash   CHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sop_version_id, user_id)
);
```

### 6.3. `sop_evidences` (append-only)

```sql
CREATE TABLE sop_evidences (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    sop_version_id  INT NOT NULL REFERENCES sop_versions(id),
    executed_by     INT REFERENCES users(id),
    execution_context JSONB NOT NULL,
    related_event_type VARCHAR(64),
    related_event_id BIGINT,
    chain_id        VARCHAR(128) NOT NULL,
    chain_sequence  BIGINT NOT NULL,
    event_hash      CHAR(64) NOT NULL,
    previous_hash   CHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chain_id, chain_sequence)
);

CREATE INDEX idx_sop_ev_tenant ON sop_evidences(tenant_id);
CREATE INDEX idx_sop_ev_version ON sop_evidences(sop_version_id);
CREATE INDEX idx_sop_ev_created ON sop_evidences(created_at);
```

### 6.4. `sop_deviations` e `capa_actions`

```sql
CREATE TABLE sop_deviations (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    sop_version_id  INT NOT NULL REFERENCES sop_versions(id),
    deviation_date  TIMESTAMPTZ NOT NULL,
    severity        VARCHAR(16) NOT NULL
                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description     TEXT NOT NULL,
    detected_by     INT REFERENCES users(id),
    status          VARCHAR(32) NOT NULL
                    CHECK (status IN ('open', 'investigating', 'capa_pending', 'resolved', 'closed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE capa_actions (
    id              SERIAL PRIMARY KEY,
    deviation_id    INT NOT NULL REFERENCES sop_deviations(id),
    action_type     VARCHAR(16) NOT NULL CHECK (action_type IN ('corrective', 'preventive')),
    description     TEXT NOT NULL,
    responsible     INT REFERENCES users(id),
    due_date        DATE NOT NULL,
    completed_at    TIMESTAMPTZ,
    effectiveness_check TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 7. Schema `traceability`

Este é o schema mais crítico. Todas as tabelas de evento são append-only e participam de cadeias de hash.

### 7.1. `genetic_matrices` e `seed_lots`

```sql
CREATE TABLE genetic_matrices (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    matrix_code     VARCHAR(64) NOT NULL,
    strain_name     VARCHAR(128),
    origin          TEXT,
    declared_profile JSONB,
    qr_code         VARCHAR(128) UNIQUE,
    nft_reference   VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, matrix_code)
);

CREATE TABLE seed_lots (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    matrix_id       INT REFERENCES genetic_matrices(id),
    lot_code        VARCHAR(64) NOT NULL,
    quantity        INT NOT NULL,
    received_at     DATE NOT NULL,
    supplier        VARCHAR(255),
    qr_code         VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, lot_code)
);
```

### 7.2. `cultivation_batches` e `plants`

```sql
CREATE TABLE cultivation_batches (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    batch_code      VARCHAR(64) NOT NULL,
    source_seed_lot_id INT REFERENCES seed_lots(id),
    source_matrix_id INT REFERENCES genetic_matrices(id),
    started_at      DATE NOT NULL,
    ended_at        DATE,
    location_description TEXT,
    geo_reference   GEOGRAPHY(POINT, 4326),
    qr_code         VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, batch_code)
);

CREATE TABLE plants (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    batch_id        INT NOT NULL REFERENCES cultivation_batches(id),
    plant_code      VARCHAR(64) NOT NULL,
    planted_at      DATE NOT NULL,
    removed_at      DATE,
    removal_reason  VARCHAR(64),
    qr_code         VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, plant_code)
);
```

### 7.3. `harvests`, `extractions`, `preparations`

```sql
CREATE TABLE harvests (
    id              SERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    batch_id        INT NOT NULL REFERENCES cultivation_batches(id),
    harvest_code    VARCHAR(64) NOT NULL,
    harvested_at    DATE NOT NULL,
    plant_ids       INT[] NOT NULL,
    gross_weight_g  NUMERIC(12,3),
    net_weight_g    NUMERIC(12,3),
    qr_code         VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, harvest_code)
);

CREATE TABLE extractions (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    harvest_id          INT NOT NULL REFERENCES harvests(id),
    extraction_code     VARCHAR(64) NOT NULL,
    executed_at         TIMESTAMPTZ NOT NULL,
    process_parameters  JSONB NOT NULL,
    sop_version_id      INT REFERENCES sop_versions(id),
    responsible_id      INT REFERENCES users(id),
    output_weight_g     NUMERIC(12,3),
    qr_code             VARCHAR(128) UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, extraction_code)
);

CREATE TABLE preparations (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    extraction_id       INT NOT NULL REFERENCES extractions(id),
    preparation_code    VARCHAR(64) NOT NULL,
    preparation_type    VARCHAR(64) NOT NULL,
    produced_at         TIMESTAMPTZ NOT NULL,
    units_produced      INT NOT NULL,
    unit_size_ml        NUMERIC(10,3),
    sop_version_id      INT REFERENCES sop_versions(id),
    warning_label_applied BOOLEAN NOT NULL DEFAULT FALSE,
    qr_code             VARCHAR(128) UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, preparation_code)
);
```

### 7.4. `lab_analyses`

```sql
CREATE TABLE lab_analyses (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    subject_type        VARCHAR(32) NOT NULL
                        CHECK (subject_type IN ('harvest', 'extraction', 'preparation')),
    subject_id          INT NOT NULL,
    lab_name            VARCHAR(255) NOT NULL,
    report_number       VARCHAR(128) NOT NULL,
    analysis_date       DATE NOT NULL,
    cannabinoid_profile JSONB NOT NULL,
    thc_percent         NUMERIC(6,3),
    cbd_percent         NUMERIC(6,3),
    conformity_status   VARCHAR(32) NOT NULL
                        CHECK (conformity_status IN ('conforming', 'non_conforming', 'pending')),
    report_uri          TEXT,
    report_hash         CHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lab_tenant ON lab_analyses(tenant_id);
CREATE INDEX idx_lab_subject ON lab_analyses(subject_type, subject_id);
```

### 7.5. `dispensations`

```sql
CREATE TABLE dispensations (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    preparation_id      INT NOT NULL REFERENCES preparations(id),
    member_id           INT NOT NULL REFERENCES association_members(id),
    prescription_id     INT NOT NULL REFERENCES prescriptions(id),
    units_dispensed     INT NOT NULL,
    dispensed_at        TIMESTAMPTZ NOT NULL,
    dispensed_by        INT REFERENCES users(id),
    warning_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    qr_code             VARCHAR(128) UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_disp_tenant ON dispensations(tenant_id);
CREATE INDEX idx_disp_member ON dispensations(member_id);
CREATE INDEX idx_disp_preparation ON dispensations(preparation_id);
CREATE INDEX idx_disp_date ON dispensations(dispensed_at);
```

### 7.6. `traceability_events` (append-only com hash chaining)

Esta é a tabela central do schema. Cada operação relevante (plantio, colheita, extração, preparação, dispensação, movimentação) gera um evento imutável.

```sql
CREATE TABLE traceability_events (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL REFERENCES tenants(id),
    event_type      VARCHAR(64) NOT NULL,
    subject_type    VARCHAR(32) NOT NULL,
    subject_id      BIGINT NOT NULL,
    actor_user_id   INT REFERENCES users(id),
    actor_role      VARCHAR(64),
    geo_reference   GEOGRAPHY(POINT, 4326),
    payload         JSONB NOT NULL,
    chain_id        VARCHAR(128) NOT NULL,
    chain_sequence  BIGINT NOT NULL,
    event_hash      CHAR(64) NOT NULL,
    previous_hash   CHAR(64),
    occurred_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chain_id, chain_sequence),
    UNIQUE (event_hash)
);

CREATE INDEX idx_trace_tenant ON traceability_events(tenant_id);
CREATE INDEX idx_trace_chain ON traceability_events(chain_id);
CREATE INDEX idx_trace_subject ON traceability_events(subject_type, subject_id);
CREATE INDEX idx_trace_type ON traceability_events(event_type);
CREATE INDEX idx_trace_occurred ON traceability_events(occurred_at);
```

### 7.7. Trigger de proteção append-only

```sql
CREATE OR REPLACE FUNCTION prevent_update_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. Updates and deletes are forbidden.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER traceability_events_immutable
    BEFORE UPDATE OR DELETE ON traceability_events
    FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();

CREATE TRIGGER sop_evidences_immutable
    BEFORE UPDATE OR DELETE ON sop_evidences
    FOR EACH ROW EXECUTE FUNCTION prevent_update_delete();
```

Aplicar trigger equivalente a todas as tabelas de evento do sistema.

### 7.8. Função de validação de cadeia

```sql
CREATE OR REPLACE FUNCTION validate_chain_continuity()
RETURNS TRIGGER AS $$
DECLARE
    expected_previous CHAR(64);
BEGIN
    SELECT event_hash INTO expected_previous
    FROM traceability_events
    WHERE chain_id = NEW.chain_id
      AND chain_sequence = NEW.chain_sequence - 1;

    IF NEW.chain_sequence > 1 AND NEW.previous_hash IS DISTINCT FROM expected_previous THEN
        RAISE EXCEPTION 'Chain continuity violation on chain %, sequence %', NEW.chain_id, NEW.chain_sequence;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER traceability_events_chain_check
    BEFORE INSERT ON traceability_events
    FOR EACH ROW EXECUTE FUNCTION validate_chain_continuity();
```

---

## 8. Schema `pharmacovigilance`

### 8.1. `adverse_events`

```sql
CREATE TABLE adverse_events (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    member_id           INT REFERENCES association_members(id),
    preparation_id      INT REFERENCES preparations(id),
    reported_at         TIMESTAMPTZ NOT NULL,
    event_onset_at      TIMESTAMPTZ,
    severity            VARCHAR(16) NOT NULL
                        CHECK (severity IN ('mild', 'moderate', 'severe', 'life_threatening', 'fatal')),
    description         TEXT NOT NULL,
    reported_via        VARCHAR(32) NOT NULL
                        CHECK (reported_via IN ('whatsapp', 'web', 'consultation', 'phone', 'other')),
    ai_triage_result    JSONB,
    triaged_by          INT REFERENCES users(id),
    clinical_assessment TEXT,
    outcome             VARCHAR(32)
                        CHECK (outcome IN ('resolved', 'resolving', 'ongoing', 'worsened', 'unknown')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ae_tenant ON adverse_events(tenant_id);
CREATE INDEX idx_ae_member ON adverse_events(member_id);
CREATE INDEX idx_ae_severity ON adverse_events(severity);
```

### 8.2. `pharmacovigilance_notifications`

```sql
CREATE TABLE pharmacovigilance_notifications (
    id                  SERIAL PRIMARY KEY,
    adverse_event_id    INT NOT NULL REFERENCES adverse_events(id),
    notification_target VARCHAR(32) NOT NULL
                        CHECK (notification_target IN ('vigimed', 'notivisa', 'internal_only')),
    notified_at         TIMESTAMPTZ NOT NULL,
    notification_reference VARCHAR(255),
    response_received_at TIMESTAMPTZ,
    response_payload    JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pv_notif_ae ON pharmacovigilance_notifications(adverse_event_id);
```

### 8.3. `sanitary_risks` e `risk_controls`

```sql
CREATE TABLE sanitary_risks (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    risk_code           VARCHAR(64) NOT NULL,
    category            VARCHAR(64) NOT NULL,
    description         TEXT NOT NULL,
    probability         VARCHAR(16) NOT NULL
                        CHECK (probability IN ('very_low', 'low', 'medium', 'high', 'very_high')),
    impact              VARCHAR(16) NOT NULL
                        CHECK (impact IN ('very_low', 'low', 'medium', 'high', 'very_high')),
    risk_level          VARCHAR(16) NOT NULL
                        CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, risk_code)
);

CREATE TABLE risk_controls (
    id                  SERIAL PRIMARY KEY,
    risk_id             INT NOT NULL REFERENCES sanitary_risks(id),
    control_description TEXT NOT NULL,
    control_type        VARCHAR(32) NOT NULL
                        CHECK (control_type IN ('preventive', 'detective', 'corrective', 'compensating')),
    responsible         INT REFERENCES users(id),
    related_sop_id      INT REFERENCES sops(id),
    last_verified_at    TIMESTAMPTZ,
    verification_status VARCHAR(32)
                        CHECK (verification_status IN ('effective', 'partial', 'ineffective', 'pending')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 9. Schema `regulatory`

### 9.1. `sandbox_projects` e `sandbox_protocols`

```sql
CREATE TABLE sandbox_projects (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    project_code        VARCHAR(64) NOT NULL,
    title               VARCHAR(255) NOT NULL,
    status              VARCHAR(32) NOT NULL
                        CHECK (status IN ('draft', 'submitted', 'under_review', 'approved',
                                          'active', 'suspended', 'concluded', 'discontinued')),
    submitted_at        TIMESTAMPTZ,
    approved_at         TIMESTAMPTZ,
    started_at          TIMESTAMPTZ,
    concluded_at        TIMESTAMPTZ,
    anvisa_reference    VARCHAR(128),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, project_code)
);

CREATE TABLE sandbox_protocols (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES sandbox_projects(id),
    protocol_version    VARCHAR(32) NOT NULL,
    scope               JSONB NOT NULL,
    applicable_norms    JSONB NOT NULL,
    modulated_norms     JSONB NOT NULL DEFAULT '{}',
    monitoring_parameters JSONB NOT NULL,
    discontinuity_plan  JSONB NOT NULL,
    quality_requirements JSONB NOT NULL,
    data_sharing_obligations JSONB NOT NULL,
    effective_from      TIMESTAMPTZ,
    effective_until     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, protocol_version)
);
```

### 9.2. `sandbox_indicators`

```sql
CREATE TABLE sandbox_indicators (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES sandbox_projects(id),
    indicator_code      VARCHAR(64) NOT NULL,
    indicator_name      VARCHAR(255) NOT NULL,
    calculation_formula TEXT NOT NULL,
    unit                VARCHAR(32),
    target_value        NUMERIC(18,4),
    reporting_frequency VARCHAR(32) NOT NULL
                        CHECK (reporting_frequency IN ('daily', 'weekly', 'monthly', 'quarterly', 'annual')),
    is_mandatory        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, indicator_code)
);

CREATE TABLE sandbox_indicator_values (
    id                  BIGSERIAL PRIMARY KEY,
    indicator_id        INT NOT NULL REFERENCES sandbox_indicators(id),
    period_start        TIMESTAMPTZ NOT NULL,
    period_end          TIMESTAMPTZ NOT NULL,
    calculated_value    NUMERIC(18,4) NOT NULL,
    calculation_details JSONB,
    calculated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_siv_indicator ON sandbox_indicator_values(indicator_id);
CREATE INDEX idx_siv_period ON sandbox_indicator_values(period_start, period_end);
```

### 9.3. `regulatory_submissions` e `regulatory_reports`

```sql
CREATE TABLE regulatory_submissions (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    project_id          INT REFERENCES sandbox_projects(id),
    submission_type     VARCHAR(64) NOT NULL,
    submitted_at        TIMESTAMPTZ NOT NULL,
    submitted_by        INT REFERENCES users(id),
    payload_uri         TEXT NOT NULL,
    payload_hash        CHAR(64) NOT NULL,
    anvisa_response_uri TEXT,
    anvisa_response_at  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE regulatory_reports (
    id                  SERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL REFERENCES tenants(id),
    project_id          INT REFERENCES sandbox_projects(id),
    report_type         VARCHAR(64) NOT NULL
                        CHECK (report_type IN ('work_plan', 'communication_plan', 'discontinuity_plan',
                                               'monitoring_plan', 'risk_management_plan',
                                               'final_monitoring_opinion', 'eligibility_dossier')),
    version             VARCHAR(32) NOT NULL,
    content_uri         TEXT NOT NULL,
    content_hash        CHAR(64) NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_by         INT REFERENCES users(id),
    approved_at         TIMESTAMPTZ
);

CREATE INDEX idx_reg_reports_tenant ON regulatory_reports(tenant_id);
CREATE INDEX idx_reg_reports_type ON regulatory_reports(report_type);
```

---

## 10. Schema `crypto`

### 10.1. `blockchain_anchors`

```sql
CREATE TABLE blockchain_anchors (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           INT REFERENCES tenants(id),
    anchor_scope        VARCHAR(32) NOT NULL
                        CHECK (anchor_scope IN ('global', 'tenant', 'project')),
    covered_from        TIMESTAMPTZ NOT NULL,
    covered_until       TIMESTAMPTZ NOT NULL,
    events_count        BIGINT NOT NULL,
    merkle_root         CHAR(64) NOT NULL,
    blockchain_network  VARCHAR(32) NOT NULL
                        CHECK (blockchain_network IN ('bitcoin_ots', 'polygon', 'ethereum')),
    transaction_id      VARCHAR(255) NOT NULL,
    block_number        BIGINT,
    block_timestamp     TIMESTAMPTZ,
    proof_uri           TEXT,
    proof_hash          CHAR(64),
    anchored_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at         TIMESTAMPTZ,
    verification_status VARCHAR(32) NOT NULL DEFAULT 'pending'
                        CHECK (verification_status IN ('pending', 'confirmed', 'failed'))
);

CREATE INDEX idx_anchors_tenant ON blockchain_anchors(tenant_id);
CREATE INDEX idx_anchors_period ON blockchain_anchors(covered_from, covered_until);
CREATE INDEX idx_anchors_network ON blockchain_anchors(blockchain_network);
```

### 10.2. `anchor_event_mappings`

Mapeia quais eventos estão cobertos por qual ancoragem.

```sql
CREATE TABLE anchor_event_mappings (
    anchor_id           BIGINT NOT NULL REFERENCES blockchain_anchors(id),
    event_table         VARCHAR(64) NOT NULL,
    event_id            BIGINT NOT NULL,
    event_hash          CHAR(64) NOT NULL,
    merkle_path         JSONB NOT NULL,
    PRIMARY KEY (anchor_id, event_table, event_id)
);
```

---

## 11. Estratégia de migrations

### 11.1. Ordem de aplicação

A série do SCC começa em **024** para preservar as migrations já existentes no repositório (`000`–`021`) e os slots **022** e **023**, reservados respectivamente para os ajustes de integridade (UNIQUE, FK, CHECK, GIN em `ai_audit_logs`) e para a padronização de `TIMESTAMPTZ` definidos no `docs/progresso17_auditoria_completa_e_melhorias.md`.

```
024_tenants_evolution.sql
025_governance_schema.sql
026_members_schema.sql
027_quality_schema.sql
028_traceability_schema_base.sql
029_traceability_hash_chaining.sql
030_traceability_triggers.sql
031_pharmacovigilance_schema.sql
032_regulatory_schema.sql
033_crypto_schema.sql
034_indexes_and_performance.sql
035_views_and_helpers.sql
036_seed_data_sandbox.sql
```

### 11.2. Princípios das migrations

- **Idempotência** — toda migration usa `IF NOT EXISTS` e é segura para re-execução.
- **Rollback possível** — toda migration tem um arquivo de rollback paralelo quando aplicável.
- **Sem destruição de dados** — nenhuma migration inicial do SCC apaga dados existentes. A migração do modelo `clinics → tenants` é feita por cópia com preservação de compatibilidade.
- **Seed opcional** — dados de seed (riscos sanitários padrão, categorias de SOP, templates de relatório) ficam em migration separada, executável em ambientes de desenvolvimento e homologação.
- **Versionamento em `schema_migrations`** — seguindo o padrão já existente no projeto.

### 11.3. Migração do modelo clinics → tenants

```sql
-- Estratégia: criar tenants como extensão compatível, não substituir clinics

-- 1. Criar tenants com discriminador
-- 2. Popular tenants a partir de clinics existentes mantendo clinic_id = tenant_id
-- 3. Adicionar tenant_id como coluna em todas as tabelas que hoje têm clinic_id
-- 4. Manter clinic_id como view ou coluna computada para retrocompatibilidade
-- 5. Novas funcionalidades usam tenant_id; código legado continua funcionando

INSERT INTO tenants (id, tenant_type, legal_name, trade_name, cnpj, plan_tier, is_active, created_at)
SELECT id, 'clinic', legal_name, trade_name, cnpj,
       COALESCE(plan_tier, 'basic'), is_active, created_at
FROM clinics
ON CONFLICT (id) DO NOTHING;

-- Sequência do tenants ajustada para acompanhar o MAX(id) de clinics
SELECT setval('tenants_id_seq', (SELECT COALESCE(MAX(id), 1) FROM tenants));
```

### 11.4. Roles e permissões

```sql
CREATE ROLE cannabia_app NOLOGIN;
CREATE ROLE cannabia_readonly NOLOGIN;
CREATE ROLE cannabia_compliance_auditor NOLOGIN;

-- Aplicação: pode ler tudo, pode inserir em tabelas mutáveis,
-- pode inserir (mas não atualizar/deletar) em tabelas append-only
GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenants, associations, technical_responsibles, institutional_documents,
    association_members, member_consents,
    sops, sop_versions, sop_trainings, sop_deviations, capa_actions,
    genetic_matrices, seed_lots, cultivation_batches, plants,
    harvests, extractions, preparations, lab_analyses, dispensations,
    adverse_events, pharmacovigilance_notifications,
    sanitary_risks, risk_controls,
    sandbox_projects, sandbox_protocols, sandbox_indicators,
    regulatory_submissions, regulatory_reports
TO cannabia_app;

GRANT SELECT, INSERT ON
    sop_evidences, traceability_events,
    sandbox_indicator_values, blockchain_anchors, anchor_event_mappings
TO cannabia_app;

-- Compliance auditor: read-only em tudo, mas com acesso direto a tabelas append-only
GRANT SELECT ON ALL TABLES IN SCHEMA public TO cannabia_compliance_auditor;
```

---

## 12. Views e helpers sugeridos

### 12.1. `v_member_active_prescriptions`

View que retorna associados ativos com prescrição válida, usada na validação de dispensação.

### 12.2. `v_traceability_chain_status`

View que mostra o estado de cada cadeia de rastreabilidade (último evento, último hash, sequência atual).

### 12.3. `v_sandbox_indicator_dashboard`

View materializada que consolida indicadores do sandbox por período para uso no dashboard regulatório.

### 12.4. `fn_generate_event_hash`

Função que calcula o hash canônico de um evento a partir de seu payload e do hash anterior.

### 12.5. `fn_verify_chain_integrity`

Função que verifica a integridade de uma cadeia inteira, útil para auditoria.

---

## 13. Considerações de performance

### 13.1. Particionamento

`traceability_events` e `sandbox_indicator_values` são candidatas naturais a particionamento por range de data, começando a partir de um volume operacional relevante (sugestão: particionar quando ultrapassar 10 milhões de registros).

### 13.2. Índices compostos adicionais

Além dos índices listados por tabela, índices compostos como `(tenant_id, occurred_at DESC)` em `traceability_events` e `(tenant_id, reported_at DESC)` em `adverse_events` aceleram os dashboards mais comuns.

### 13.3. JSONB vs colunas

Campos altamente estruturados e consultados como filtro (severidade, status) ficam como colunas tipadas. Campos semi-estruturados ou com evolução esperada (perfis de canabinoides, payloads, scores) ficam como JSONB com índices GIN quando necessário.

---

## 14. Estratégia de testes

### 14.1. Testes de integridade

Para cada tabela append-only:

- Tentar UPDATE — deve falhar.
- Tentar DELETE — deve falhar.
- Inserir com `previous_hash` incorreto — deve falhar.
- Inserir em sequência — deve validar a cadeia.

### 14.2. Testes de validação de dispensação

- Dispensar para associado inativo — deve falhar.
- Dispensar sem prescrição válida — deve falhar.
- Dispensar preparação sem laudo analítico — deve falhar quando política exigir.
- Dispensar sem advertência de não-medicamento — deve falhar.

### 14.3. Testes de ancoragem

- Gerar conjunto de eventos — calcular raiz Merkle — ancorar — verificar prova.
- Tentar ancoragem com eventos adulterados — deve produzir prova inválida ao verificar.

### 14.4. Testes de LGPD

- Apagar PII de um associado — cadeia de eventos permanece íntegra.
- Verificar que PII não aparece em nenhum payload de evento.
- Verificar que hash de evento não é reversível a PII.

---

## 15. Pontos para aprofundamento posterior

- Estratégia detalhada de particionamento por volume real.
- Decisão final sobre ENUM nativo vs VARCHAR com CHECK.
- Política de backup e restauração específica das tabelas append-only.
- Modelo de auditoria de consultas (quem consultou o quê e quando).
- Especificação completa das views materializadas e sua cadência de refresh.
- Migração de dados históricos pré-SCC para o novo modelo quando aplicável.
- Integração com SNGPC em nível de schema (campos específicos exigidos).

---

## 16. Regras aprovadas neste documento

Ficam aprovadas como base oficial:

- Tenants evoluem como entidade genérica; clinics mantém retrocompatibilidade.
- Eventos são append-only e participam de cadeias de hash.
- Contexto com PII é separado de eventos imutáveis.
- Triggers de banco impedem UPDATE e DELETE em tabelas append-only.
- Roles de aplicação não têm permissão de UPDATE ou DELETE em tabelas de evento.
- Cada dispensação valida associado ativo, prescrição válida e advertência de não-medicamento.
- Ancoragens em blockchain têm seu próprio schema e mapeamento detalhado de eventos cobertos.
- Migrations seguem numeração sequencial, com idempotência e rollback sempre que aplicável.
- JSONB é usado para estruturas evolutivas; colunas tipadas para filtros operacionais.
- Views e funções consolidam lógica transversal e padronizam o acesso dos serviços.

---

## 17. Conclusão

Este documento transforma a modelagem lógica do SCC em especificação física concreta, pronta para materializar em migrations SQL.

A arquitetura respeita os três princípios centrais da proposta do SCC: **rastreabilidade imutável, separação estrutural entre evento e PII, e verificabilidade independente**. Ela se encaixa no modelo atual da CannabIA sem romper compatibilidade, e cria a base sólida sobre a qual o Protocolo de Ancoragem em Blockchain e a Biblioteca de Templates Regulatórios serão construídos nos documentos subsequentes.
