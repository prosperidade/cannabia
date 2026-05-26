-- Migration 047: Medical profile (doctor credentialing data).
--
-- Sprint C track MVP: persistir o resultado do wizard /med/onboarding,
-- que antes era "All data is mock/UI only" (frontend page.tsx linha 16-17).
--
-- Perfil 1:1 com users (user_id UNIQUE). Cobre apenas usuarios com role
-- Medico — outros roles nao tem perfil profissional aqui.
--
-- Upload de documentos (CRM, diploma) fica como coluna URL nullable: o
-- backend de storage real (S3 / Render disk) chega numa onda 2 desta
-- sprint. Por enquanto, o frontend mostra placeholders desabilitados.

CREATE TABLE IF NOT EXISTS medical_profiles (
    id                        SERIAL PRIMARY KEY,
    user_id                   INTEGER NOT NULL UNIQUE
                                REFERENCES users(id) ON DELETE CASCADE,
    full_name                 VARCHAR(255) NOT NULL DEFAULT '',
    crm                       VARCHAR(20)  NOT NULL DEFAULT '',
    specialty                 VARCHAR(100) NOT NULL DEFAULT '',
    photo_url                 TEXT,
    crm_doc_url               TEXT,
    diploma_url               TEXT,
    prefs_notifications       BOOLEAN      NOT NULL DEFAULT TRUE,
    prefs_ai_level            VARCHAR(20)  NOT NULL DEFAULT 'avancado',
    onboarding_completed_at   TIMESTAMPTZ,
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_medical_profiles_completed
    ON medical_profiles(onboarding_completed_at)
    WHERE onboarding_completed_at IS NOT NULL;

COMMENT ON TABLE  medical_profiles                         IS 'Sprint C MVP: perfil profissional do medico (onboarding)';
COMMENT ON COLUMN medical_profiles.prefs_ai_level          IS 'Sprint C MVP: nivel de assistencia da IA (basico|avancado|completo)';
COMMENT ON COLUMN medical_profiles.crm_doc_url             IS 'Sprint C MVP: URL do upload da copia do CRM (NULL ate onda 2 com storage)';
COMMENT ON COLUMN medical_profiles.diploma_url             IS 'Sprint C MVP: URL do upload do diploma de graduacao (NULL ate onda 2 com storage)';
COMMENT ON COLUMN medical_profiles.onboarding_completed_at IS 'Sprint C MVP: timestamp do completar; NULL = wizard nao concluido';
