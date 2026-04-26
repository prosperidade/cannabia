-- Migration 039: tenant_settings (JSONB) — backing store para a tela
-- /org/configuracoes (UI moderna com 6 abas).
--
-- Decisao de schema: ao inves de criar 4-5 tabelas dedicadas (operacional,
-- integracoes, dna, notificacoes), usamos UMA tabela JSONB unica por tenant.
-- Razoes:
--   - Os campos sao todos por tenant (cardinalidade 1:1)
--   - Esquema e flexivel — vamos iterar muito na fase A2
--   - Nao precisa de migration cada vez que a UI ganha um campo
--   - Persistencia simples (UPSERT + JSONB merge)
--
-- Estrutura esperada de `settings`:
--   {
--     "cadastro":       { "cnpj", "address", "phone", "email" },
--     "operacional":    { "weekdayOpen", "weekdayClose", "weekendOpen",
--                         "weekendClose", "sundayClosed",
--                         "consultationPrice", "consultationDuration",
--                         "modalityPresencial", "modalityOnline" },
--     "integracoes":    { "whatsappNumber",
--                         "apiKeyMeta",   ← chaves sensiveis (mvp: claro)
--                         "apiKeyOpenAI",
--                         "apiKeyGemini",
--                         "smtpHost", "smtpUser", "smtpPassword" },
--     "businessDna":    { "businessMission", "targetPatientProfile",
--                         "agentToneOfVoice", "internalPolicies" },
--     "notificacoes":   { "notifyEmailNewPatient", "notifyEmailAppointment",
--                         "notifyEmailBilling", "notifyWhatsappReminder",
--                         "notifyWhatsappFollowup", "notifyWhatsappBilling" }
--   }
--
-- Identidade visual (brandName, logoUrl, primaryColor, secondaryColor,
-- subdomain) continua em `tenant_branding` (tabela existente).
-- Razao social `name` continua em `clinics.name`.
--
-- Idempotente: CREATE TABLE IF NOT EXISTS.
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenant_settings (
    tenant_id   INT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    settings    JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by  INT REFERENCES users(id) ON DELETE SET NULL
);

COMMENT ON TABLE tenant_settings IS
    'Configuracoes do tenant em JSONB unico. Backing store da tela '
    '/org/configuracoes — categorias: cadastro, operacional, integracoes, '
    'businessDna, notificacoes. Chaves sensiveis (API tokens, SMTP password) '
    'ficam em texto plano em DEV; em PROD devem ser criptografadas via '
    'tenant_secrets (sprint futura).';

CREATE INDEX IF NOT EXISTS idx_tenant_settings_updated
    ON tenant_settings (updated_at DESC);
