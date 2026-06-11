-- migrations/050_inbound_idempotency.sql
-- Track B / COM-1 (doc 30 Onda 1; docs/29.3 RM1)
-- Idempotencia de mensagens inbound do WhatsApp:
--   * incoming_messages.wamid (id da Meta) + indice unico parcial (clinic_id, wamid)
--   * indice unico parcial em conversation_messages(external_id)
-- Reentrega da Meta (redelivery por ate 7 dias quando nao recebe 200 em ~5s) deixa
-- de duplicar mensagem e de avancar 2x a maquina de estados (29.3 P1/RM1).
-- Aditiva e idempotente. Down em migrations/down/050_inbound_idempotency_down.sql
-- ============================================================================

-- ETAPA 1 — coluna wamid (nullable; linhas legadas permanecem com NULL)
ALTER TABLE incoming_messages ADD COLUMN IF NOT EXISTS wamid VARCHAR(255);

-- ETAPA 2 — limpeza defensiva de duplicatas pre-existentes de external_id em
-- conversation_messages ANTES de criar o indice unico (mantem o menor id).
-- Em base limpa e no-op. Necessaria porque external_id nunca teve unicidade.
DELETE FROM conversation_messages cm
USING conversation_messages dup
WHERE cm.external_id IS NOT NULL
  AND cm.external_id = dup.external_id
  AND cm.id > dup.id;

-- ETAPA 3 — indice unico parcial (clinic_id, wamid): impede duplicar a mesma
-- mensagem Meta na mesma clinica. Linhas sem wamid (legado) nao participam.
CREATE UNIQUE INDEX IF NOT EXISTS uq_incoming_messages_clinic_wamid
    ON incoming_messages (clinic_id, wamid)
    WHERE wamid IS NOT NULL;

-- ETAPA 4 — indice unico parcial em conversation_messages(external_id):
-- defesa-em-profundidade no threading de conversas contra reentrega Meta.
CREATE UNIQUE INDEX IF NOT EXISTS uq_conversation_messages_external_id
    ON conversation_messages (external_id)
    WHERE external_id IS NOT NULL;
