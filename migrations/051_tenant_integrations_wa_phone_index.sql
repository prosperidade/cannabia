-- migrations/051_tenant_integrations_wa_phone_index.sql
-- Track B / COM-3 (doc 30 Onda 1; docs/29.3 RM5)
-- Indice unico parcial em tenant_integrations(whatsapp_phone_number_id):
-- base do roteamento multi-tenant do webhook Meta (resolver tenant a partir de
-- value.metadata.phone_number_id). Garante 1 tenant por numero e acelera o lookup.
-- Aditiva e idempotente. Down em migrations/down/051_tenant_integrations_wa_phone_index_down.sql
-- ============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_integrations_wa_phone_number_id
    ON tenant_integrations (whatsapp_phone_number_id)
    WHERE whatsapp_phone_number_id IS NOT NULL;
