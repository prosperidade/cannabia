-- Migration 043: Telemetria do AgentePrescritor em ai_audit_logs.
--
-- Sprint 1 Track C.1 inseriu o AgentePrescritor como 4o stage do
-- clinical_flow (Anamnese -> Tratamento -> Prescritor -> Cientifico).
-- Audit log precisa registrar tempo e tokens dessa etapa para que o
-- cost-per-stage em service.py reflita o custo real (4 stages, nao 3)
-- e para que dashboards/relatorios mostrem latencia da etapa.
--
-- Esta migration adiciona as 3 colunas. save_ai_audit_log() em
-- ai_audit_repository.py foi atualizada na mesma PR para popular esses
-- campos a partir do dict result["timings_ms"] e result["tokens_per_stage"].
--
-- Schema: as colunas sao nullable porque audit log pode ser gravado em
-- estados early (billing_blocked, security_blocked, validation_error)
-- onde o flow nem chegou a rodar o Prescritor.

ALTER TABLE ai_audit_logs
  ADD COLUMN prescription_time_ms      INTEGER,
  ADD COLUMN prescription_input_tokens INTEGER,
  ADD COLUMN prescription_output_tokens INTEGER;

COMMENT ON COLUMN ai_audit_logs.prescription_time_ms      IS 'Latencia do stage Prescritor em ms (Sprint 1 C.1)';
COMMENT ON COLUMN ai_audit_logs.prescription_input_tokens IS 'Tokens de input do Prescritor LLM (gpt-4o-mini)';
COMMENT ON COLUMN ai_audit_logs.prescription_output_tokens IS 'Tokens de output do Prescritor LLM';
