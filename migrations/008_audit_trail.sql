-- migrations/008_audit_trail.sql
-- Trilha de auditoria transversal para ações clínicas e administrativas.
--
-- Registra: quem fez o quê, quando, de onde, e o estado antes/depois.
-- Complementa a auditoria de IA (ai_audit_logs) com cobertura de
-- login, prontuário, agendamentos e operações administrativas.

CREATE TABLE IF NOT EXISTS audit_trail (
    id             BIGSERIAL    PRIMARY KEY,
    clinic_id      INT          NOT NULL,
    tenant_id      INT          DEFAULT NULL,
    user_id        INT          DEFAULT NULL,
    action         VARCHAR(100) NOT NULL,
    resource_type  VARCHAR(100) NOT NULL,
    resource_id    VARCHAR(100) DEFAULT NULL,
    details        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    ip_address     VARCHAR(45)  DEFAULT NULL,
    user_agent     TEXT         DEFAULT NULL,
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índices orientados às consultas mais comuns de auditoria
CREATE INDEX IF NOT EXISTS idx_audit_trail_clinic_created
    ON audit_trail (clinic_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_trail_user_created
    ON audit_trail (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_trail_resource
    ON audit_trail (resource_type, resource_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_trail_action
    ON audit_trail (action, created_at DESC);
