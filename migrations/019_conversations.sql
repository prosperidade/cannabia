-- Migration 019: Conversations — modelo de threads para inbox clinica
-- Sprint 3: comunicacao e WhatsApp

-- =====================================================
-- 1. Tabela de conversas (thread por paciente/contato)
-- =====================================================
CREATE TABLE IF NOT EXISTS conversations (
    id              SERIAL PRIMARY KEY,
    clinic_id       INT          NOT NULL,
    patient_id      INT,
    contact_phone   VARCHAR(30)  NOT NULL,
    contact_name    VARCHAR(200),
    channel         VARCHAR(20)  NOT NULL DEFAULT 'whatsapp',
    status          VARCHAR(20)  NOT NULL DEFAULT 'open',
    assigned_to     INT,
    last_message_at TIMESTAMPTZ,
    last_message_preview TEXT,
    unread_count    INT          NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_conversations_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id),
    CONSTRAINT fk_conversations_patient
        FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_conversations_assigned
        FOREIGN KEY (assigned_to) REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_clinic_phone
    ON conversations (clinic_id, contact_phone);

CREATE INDEX IF NOT EXISTS idx_conversations_clinic_status
    ON conversations (clinic_id, status, last_message_at DESC);

-- =====================================================
-- 2. Tabela de mensagens da conversa (thread messages)
-- =====================================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              SERIAL PRIMARY KEY,
    conversation_id INT          NOT NULL,
    clinic_id       INT          NOT NULL,
    direction       VARCHAR(10)  NOT NULL DEFAULT 'inbound',
    sender_type     VARCHAR(20)  NOT NULL DEFAULT 'patient',
    sender_name     VARCHAR(200),
    message_text    TEXT,
    message_type    VARCHAR(20)  NOT NULL DEFAULT 'text',
    external_id     VARCHAR(100),
    status          VARCHAR(20)  NOT NULL DEFAULT 'delivered',
    metadata        JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_conv_messages_conversation
        FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    CONSTRAINT fk_conv_messages_clinic
        FOREIGN KEY (clinic_id) REFERENCES clinics(id)
);

CREATE INDEX IF NOT EXISTS idx_conv_messages_conversation
    ON conversation_messages (conversation_id, created_at);

-- =====================================================
-- 3. Vincular incoming_messages a conversations
-- =====================================================
ALTER TABLE incoming_messages
    ADD COLUMN IF NOT EXISTS conversation_id INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_incoming_messages_conversation'
          AND table_name = 'incoming_messages'
    ) THEN
        ALTER TABLE incoming_messages
            ADD CONSTRAINT fk_incoming_messages_conversation
            FOREIGN KEY (conversation_id) REFERENCES conversations(id);
    END IF;
END
$$;
