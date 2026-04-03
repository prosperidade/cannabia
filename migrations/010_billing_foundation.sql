-- 010_billing_foundation.sql
-- Camada de Monetização B2B (Fase 5.3)
--
-- Arquitetura:
--   billing_plans          — catálogo de planos disponíveis (Free, Starter, Professional, Enterprise)
--   billing_subscriptions  — vínculo tenant ↔ plano (1 ativa por tenant)
--   billing_usage          — registro de consumo de IA por tenant/mês (contagem + tokens)
--   billing_events         — log imutável de eventos de billing (upgrade, downgrade, limit_hit, etc.)
--
-- Enforcement:
--   - soft_limit: aviso ao usuário (ex: 80% do limite)
--   - hard_limit: bloqueia novas chamadas de IA até reset do ciclo

BEGIN;

-- ─── Planos de assinatura ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_plans (
    id                  SERIAL PRIMARY KEY,
    slug                VARCHAR(50) NOT NULL UNIQUE,      -- "free", "starter", "professional", "enterprise"
    display_name        VARCHAR(100) NOT NULL,
    description         TEXT,

    -- Limites de IA por ciclo de billing (mensal)
    ai_requests_limit   INTEGER NOT NULL DEFAULT 0,       -- 0 = ilimitado
    ai_tokens_limit     INTEGER NOT NULL DEFAULT 0,       -- 0 = ilimitado
    max_patients        INTEGER NOT NULL DEFAULT 0,       -- 0 = ilimitado
    max_users           INTEGER NOT NULL DEFAULT 0,       -- 0 = ilimitado

    -- Thresholds de aviso
    soft_limit_pct      INTEGER NOT NULL DEFAULT 80,      -- % do limite para emitir aviso

    -- Pricing (centavos USD para evitar float)
    price_cents_monthly INTEGER NOT NULL DEFAULT 0,
    price_cents_yearly  INTEGER NOT NULL DEFAULT 0,

    -- Funcionalidades habilitadas
    features            JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- Ex: {"rag": true, "async": true, "whatsapp_campaigns": false, "priority_support": false}

    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Seed de planos padrão ───────────────────────────────────────────────────
INSERT INTO billing_plans (slug, display_name, description, ai_requests_limit, ai_tokens_limit, max_patients, max_users, soft_limit_pct, price_cents_monthly, price_cents_yearly, features, sort_order)
VALUES
    ('free', 'Free', 'Plano gratuito para avaliação', 50, 100000, 20, 2, 80, 0, 0,
     '{"rag": false, "async": false, "whatsapp_campaigns": false, "priority_support": false}'::JSONB, 1),

    ('starter', 'Starter', 'Para clínicas pequenas', 500, 1000000, 200, 5, 80, 9900, 99900,
     '{"rag": true, "async": true, "whatsapp_campaigns": false, "priority_support": false}'::JSONB, 2),

    ('professional', 'Professional', 'Para clínicas de médio porte', 2000, 5000000, 1000, 20, 80, 29900, 299900,
     '{"rag": true, "async": true, "whatsapp_campaigns": true, "priority_support": false}'::JSONB, 3),

    ('enterprise', 'Enterprise', 'Para redes de clínicas', 0, 0, 0, 0, 90, 0, 0,
     '{"rag": true, "async": true, "whatsapp_campaigns": true, "priority_support": true}'::JSONB, 4)
ON CONFLICT (slug) DO NOTHING;

-- ─── Assinaturas (vínculo tenant ↔ plano) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id                  SERIAL PRIMARY KEY,
    clinic_id           INTEGER NOT NULL,
    plan_id             INTEGER NOT NULL REFERENCES billing_plans(id),
    status              VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'past_due', 'cancelled', 'trial')),

    -- Ciclo de billing
    billing_cycle       VARCHAR(10) NOT NULL DEFAULT 'monthly'
                        CHECK (billing_cycle IN ('monthly', 'yearly')),
    current_period_start TIMESTAMPTZ NOT NULL DEFAULT DATE_TRUNC('month', NOW()),
    current_period_end   TIMESTAMPTZ NOT NULL DEFAULT DATE_TRUNC('month', NOW()) + INTERVAL '1 month',

    -- Metadados
    trial_ends_at       TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Máximo 1 assinatura ativa por tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_sub_active_per_clinic
    ON billing_subscriptions (clinic_id)
    WHERE status IN ('active', 'trial');

CREATE INDEX IF NOT EXISTS idx_billing_sub_plan ON billing_subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_status ON billing_subscriptions(status);

-- ─── Registro de consumo mensal ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_usage (
    id                  SERIAL PRIMARY KEY,
    clinic_id           INTEGER NOT NULL,
    period_start        DATE NOT NULL,                    -- primeiro dia do mês
    period_end          DATE NOT NULL,                    -- último dia do mês

    -- Contadores
    ai_requests_count   INTEGER NOT NULL DEFAULT 0,
    ai_tokens_used      INTEGER NOT NULL DEFAULT 0,
    patients_count      INTEGER NOT NULL DEFAULT 0,

    -- Flags de enforcement
    soft_limit_hit      BOOLEAN NOT NULL DEFAULT FALSE,
    hard_limit_hit      BOOLEAN NOT NULL DEFAULT FALSE,
    soft_limit_hit_at   TIMESTAMPTZ,
    hard_limit_hit_at   TIMESTAMPTZ,

    -- Estimativa de custo (centavos USD)
    estimated_cost_cents INTEGER NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 1 registro de usage por tenant por mês
    CONSTRAINT uq_billing_usage_per_period UNIQUE (clinic_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_billing_usage_clinic ON billing_usage(clinic_id);
CREATE INDEX IF NOT EXISTS idx_billing_usage_period ON billing_usage(period_start);

-- ─── Log de eventos de billing (imutável) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS billing_events (
    id                  BIGSERIAL PRIMARY KEY,
    clinic_id           INTEGER NOT NULL,
    event_type          VARCHAR(50) NOT NULL,
    -- Tipos: "subscription_created", "plan_upgraded", "plan_downgraded",
    --        "soft_limit_hit", "hard_limit_hit", "limit_reset",
    --        "payment_received", "payment_failed", "subscription_cancelled"
    details             JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_billing_events_clinic ON billing_events(clinic_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_events_type ON billing_events(event_type, created_at DESC);

COMMIT;
