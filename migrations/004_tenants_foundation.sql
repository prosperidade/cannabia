-- migrations/004_tenants_foundation.sql
-- Fundação inicial de tenancy ampla, preservando compatibilidade com clinic_id

CREATE TABLE IF NOT EXISTS tenant_types (
    id         SERIAL PRIMARY KEY,
    slug       VARCHAR(50)  NOT NULL UNIQUE,
    label      VARCHAR(100) NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO tenant_types (slug, label)
VALUES ('clinic', 'Clínica')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tenant_types (slug, label)
VALUES ('association', 'Associação')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO tenant_types (slug, label)
VALUES ('doctor', 'Médico')
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS tenants (
    id               SERIAL PRIMARY KEY,
    tenant_type_id   INT           NOT NULL,
    legal_name       VARCHAR(255)  NOT NULL,
    display_name     VARCHAR(255)  NOT NULL,
    slug             VARCHAR(64)   NOT NULL UNIQUE,
    status           VARCHAR(50)   NOT NULL DEFAULT 'active',
    legacy_clinic_id INT           UNIQUE,
    created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tenants_type
        FOREIGN KEY (tenant_type_id) REFERENCES tenant_types(id)
);

CREATE TABLE IF NOT EXISTS tenant_branding (
    tenant_id        INT           PRIMARY KEY,
    brand_name       VARCHAR(255),
    logo_url         TEXT,
    primary_color    VARCHAR(20),
    secondary_color  VARCHAR(20),
    subdomain        VARCHAR(120),
    created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tenant_branding_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS tenant_integrations (
    tenant_id                        INT           PRIMARY KEY,
    whatsapp_phone_number_id         VARCHAR(120),
    whatsapp_business_account_id     VARCHAR(120),
    meta_whatsapp_key_encrypted      TEXT,
    email_from                       VARCHAR(255),
    smtp_server                      VARCHAR(255),
    smtp_port                        INT,
    email_password_encrypted         TEXT,
    ai_provider                      VARCHAR(50),
    ai_api_key_encrypted             TEXT,
    created_at                       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tenant_integrations_tenant
        FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);

CREATE TABLE IF NOT EXISTS user_tenant_roles (
    user_id          INT           NOT NULL,
    tenant_id        INT           NOT NULL,
    role             VARCHAR(50)   NOT NULL,
    is_default       BOOLEAN       NOT NULL DEFAULT FALSE,
    source_clinic_id INT           DEFAULT NULL,
    created_at       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, tenant_id, role)
);

ALTER TABLE clinics
ADD COLUMN IF NOT EXISTS tenant_id INT;

CREATE INDEX IF NOT EXISTS idx_clinics_tenant_id
    ON clinics (tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_tenant_roles_tenant_id
    ON user_tenant_roles (tenant_id);

INSERT INTO tenants (
    tenant_type_id,
    legal_name,
    display_name,
    slug,
    status,
    legacy_clinic_id
)
SELECT
    tt.id,
    c.name,
    c.name,
    c.slug,
    CASE
        WHEN c.is_active THEN 'active'
        ELSE 'inactive'
    END,
    c.id
FROM clinics c
JOIN tenant_types tt
  ON tt.slug = 'clinic'
WHERE NOT EXISTS (
    SELECT 1
    FROM tenants t
    WHERE t.legacy_clinic_id = c.id
);

UPDATE clinics c
SET tenant_id = t.id
FROM tenants t
WHERE t.legacy_clinic_id = c.id
  AND (c.tenant_id IS NULL OR c.tenant_id <> t.id);

INSERT INTO tenant_branding (tenant_id, brand_name)
SELECT t.id, t.display_name
FROM tenants t
WHERE NOT EXISTS (
    SELECT 1
    FROM tenant_branding tb
    WHERE tb.tenant_id = t.id
);

INSERT INTO user_tenant_roles (
    user_id,
    tenant_id,
    role,
    is_default,
    source_clinic_id
)
SELECT
    uc.user_id,
    c.tenant_id,
    uc.role,
    uc.is_default,
    uc.clinic_id
FROM user_clinics uc
JOIN clinics c
  ON c.id = uc.clinic_id
WHERE c.tenant_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM user_tenant_roles utr
      WHERE utr.user_id = uc.user_id
        AND utr.tenant_id = c.tenant_id
        AND utr.role = uc.role
  );
