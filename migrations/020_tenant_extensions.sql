-- Migration 020: Tenant extensions — billing plan, quota, subdomain uniqueness, extra secrets
-- Sprint 6: multi-tenancy e white-label

-- =====================================================
-- 1. Plano comercial e quotas por tenant
-- =====================================================
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS billing_plan VARCHAR(32) NOT NULL DEFAULT 'starter';

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS ai_executions_month INT NOT NULL DEFAULT 0;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS ai_limit_month INT NOT NULL DEFAULT 1000;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS user_limit INT NOT NULL DEFAULT 10;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS quota_reset_at TIMESTAMP;

-- =====================================================
-- 2. Unicidade do subdominio de branding
-- =====================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_branding_subdomain
    ON tenant_branding (LOWER(subdomain))
    WHERE subdomain IS NOT NULL AND subdomain <> '';

-- =====================================================
-- 3. Segredos extras por tenant
-- =====================================================
ALTER TABLE tenant_integrations
    ADD COLUMN IF NOT EXISTS whatsapp_app_secret_encrypted TEXT;

ALTER TABLE tenant_integrations
    ADD COLUMN IF NOT EXISTS verify_token_encrypted TEXT;

ALTER TABLE tenant_integrations
    ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT;

ALTER TABLE tenant_integrations
    ADD COLUMN IF NOT EXISTS doctor_email VARCHAR(255);

-- =====================================================
-- 4. Indice de busca de tenant por slug (case-insensitive)
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_tenants_slug_lower
    ON tenants (LOWER(slug));
