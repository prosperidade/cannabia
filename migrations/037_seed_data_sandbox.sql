-- Migration 037: Seed data sandbox (F6.3 do docs/BACKLOG_SCC.md)
--
-- Cria a funcao `seed_sandbox_defaults(tenant_id)` que popula o
-- catalogo padrao de sandbox para um tenant especifico. NAO popula
-- ninguem automaticamente — opt-in via chamada explicita:
--
--   SELECT * FROM seed_sandbox_defaults(<tenant_id>);
--
-- Por que funcao em vez de INSERTs diretos: as tabelas sanitary_risks
-- e sops tem `tenant_id NOT NULL` com UNIQUE (tenant_id, code). Inserir
-- direto na migration acoplaria o seed a um tenant especifico e/ou
-- exigiria iterar sobre todos os tenants existentes — comportamento
-- inadequado em producao. Funcao opt-in mantem o catalogo como
-- biblioteca disponivel sem tocar dados sem permissao.
--
-- Conteudo do catalogo:
--   - 10 sanitary_risks padrao do dominio cannabis sandbox
--     (contaminacao, dosagem, interacao, PV, trace, LGPD, supply,
--      regulatorio).
--   - 10 sops padrao cobrindo as 6 areas operacionais
--     (cultivation, extraction, quality_control, dispensation,
--      pharmacovigilance, governance).
--
-- "Templates de relatorio" mencionados no BACKLOG sao file-based em
-- data/templates/registry.yaml e nao se aplicam a esta migration.
--
-- Numeracao 037: deslocamento propaga das migrations 035 e 036 que
-- moveram +1 do que o BACKLOG previa por causa de colisoes anteriores.
--
-- Idempotente: CREATE OR REPLACE na funcao + ON CONFLICT DO NOTHING
-- nos inserts.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- seed_sandbox_defaults(tenant_id)
--
-- Retorna TABLE (object_type TEXT, inserted INT) com a contagem de
-- linhas efetivamente inseridas (nao conta CONFLICT skips).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION seed_sandbox_defaults(p_tenant_id INT)
RETURNS TABLE (object_type TEXT, inserted INT)
LANGUAGE plpgsql
AS $$
DECLARE
    v_risks_inserted INT := 0;
    v_sops_inserted  INT := 0;
BEGIN
    -- Validacao: tenant precisa existir
    IF NOT EXISTS (SELECT 1 FROM tenants WHERE id = p_tenant_id) THEN
        RAISE EXCEPTION 'Tenant % nao existe', p_tenant_id;
    END IF;

    -- ---------------------------------------------------------------
    -- Sanitary risks: 10 riscos padrao
    -- Probabilidade x Impacto -> risk_level (matriz simplificada).
    -- ---------------------------------------------------------------
    WITH ins AS (
      INSERT INTO sanitary_risks
        (tenant_id, risk_code, category, description,
         probability, impact, risk_level, is_active)
      VALUES
        (p_tenant_id, 'RISK-CONT-001', 'contamination',
         'Contaminacao microbiologica em extratos e preparacoes',
         'medium', 'high', 'high', TRUE),
        (p_tenant_id, 'RISK-CONT-002', 'contamination',
         'Residuos de pesticidas, solventes ou metais pesados acima do limite',
         'low', 'high', 'medium', TRUE),
        (p_tenant_id, 'RISK-DOSE-001', 'dispensation',
         'Erro de dosagem ou rotulagem incorreta na dispensacao ao associado',
         'medium', 'high', 'high', TRUE),
        (p_tenant_id, 'RISK-DOSE-002', 'production',
         'Variacao significativa de teor de canabinoides entre lotes',
         'medium', 'medium', 'medium', TRUE),
        (p_tenant_id, 'RISK-INTER-001', 'clinical',
         'Interacao medicamentosa relevante nao detectada na prescricao',
         'low', 'high', 'medium', TRUE),
        (p_tenant_id, 'RISK-PV-001', 'pharmacovigilance',
         'Subnotificacao de eventos adversos por pacientes ou prescritores',
         'high', 'medium', 'high', TRUE),
        (p_tenant_id, 'RISK-TRACE-001', 'traceability',
         'Perda de rastreabilidade seed-to-patient (cadeia de custodia)',
         'low', 'very_high', 'critical', TRUE),
        (p_tenant_id, 'RISK-DATA-001', 'data_protection',
         'Vazamento de PII de pacientes ou associados (LGPD)',
         'low', 'very_high', 'critical', TRUE),
        (p_tenant_id, 'RISK-SUPPL-001', 'supply_chain',
         'Falha de fornecedor de materia-prima ou laboratorio terceirizado',
         'medium', 'medium', 'medium', TRUE),
        (p_tenant_id, 'RISK-LEGAL-001', 'regulatory',
         'Mudanca regulatoria significativa durante o experimento',
         'medium', 'high', 'high', TRUE)
      ON CONFLICT (tenant_id, risk_code) DO NOTHING
      RETURNING 1
    )
    SELECT COUNT(*)::int INTO v_risks_inserted FROM ins;

    -- ---------------------------------------------------------------
    -- SOPs: 10 procedimentos padrao em 6 areas
    -- Inseridos sem versao (current_version_id NULL) — RT cria a v1
    -- e atualiza current_version_id quando aprovar a primeira revisao.
    -- ---------------------------------------------------------------
    WITH ins AS (
      INSERT INTO sops (tenant_id, code, title, area, is_active)
      VALUES
        (p_tenant_id, 'SOP-CULT-001',
         'Manejo de cultivo: irrigacao, nutricao e poda', 'cultivation', TRUE),
        (p_tenant_id, 'SOP-CULT-002',
         'Colheita, secagem e cura de inflorescencias', 'cultivation', TRUE),
        (p_tenant_id, 'SOP-EXT-001',
         'Extracao de oleos full-spectrum e isolados', 'extraction', TRUE),
        (p_tenant_id, 'SOP-QC-001',
         'Analise de teor de canabinoides por HPLC', 'quality_control', TRUE),
        (p_tenant_id, 'SOP-QC-002',
         'Analise microbiologica e de metais pesados', 'quality_control', TRUE),
        (p_tenant_id, 'SOP-DISP-001',
         'Dispensacao ao associado: conferencia, rotulagem e registro',
         'dispensation', TRUE),
        (p_tenant_id, 'SOP-PV-001',
         'Captura de eventos adversos via WhatsApp e consulta',
         'pharmacovigilance', TRUE),
        (p_tenant_id, 'SOP-PV-002',
         'Notificacao a ANVISA via VigiMed/Notivisa', 'pharmacovigilance', TRUE),
        (p_tenant_id, 'SOP-GOV-001',
         'Atualizacao de documentos institucionais e versionamento',
         'governance', TRUE),
        (p_tenant_id, 'SOP-GOV-002',
         'Habilitacao do Responsavel Tecnico e renovacao anual',
         'governance', TRUE)
      ON CONFLICT (tenant_id, code) DO NOTHING
      RETURNING 1
    )
    SELECT COUNT(*)::int INTO v_sops_inserted FROM ins;

    -- ---------------------------------------------------------------
    -- Retorno: 1 linha por tipo de objeto seedado
    -- ---------------------------------------------------------------
    RETURN QUERY
      SELECT 'sanitary_risks'::TEXT, v_risks_inserted
      UNION ALL
      SELECT 'sops'::TEXT, v_sops_inserted;
END;
$$;


-- ---------------------------------------------------------------------------
-- Helper: chamar seed_sandbox_defaults para todos os tenants do tipo
-- 'association' que ainda nao tem nenhum sanitary_risk cadastrado.
--
-- Util em ambiente de demo/homologacao: SELECT seed_sandbox_defaults_all_associations();
-- Em producao, usar com cautela — popula multiplos tenants de uma vez.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION seed_sandbox_defaults_all_associations()
RETURNS TABLE (tenant_id INT, sanitary_risks INT, sops INT)
LANGUAGE plpgsql
AS $$
DECLARE
    rec RECORD;
    seed_result RECORD;
    v_risks INT;
    v_sops  INT;
BEGIN
    FOR rec IN
      SELECT t.id
        FROM tenants t
       WHERE t.tenant_type = 'association'
         AND NOT EXISTS (
           SELECT 1 FROM sanitary_risks sr WHERE sr.tenant_id = t.id
         )
    LOOP
        v_risks := 0;
        v_sops  := 0;
        FOR seed_result IN SELECT * FROM seed_sandbox_defaults(rec.id) LOOP
            IF seed_result.object_type = 'sanitary_risks' THEN
                v_risks := seed_result.inserted;
            ELSIF seed_result.object_type = 'sops' THEN
                v_sops := seed_result.inserted;
            END IF;
        END LOOP;
        tenant_id      := rec.id;
        sanitary_risks := v_risks;
        sops           := v_sops;
        RETURN NEXT;
    END LOOP;
END;
$$;


-- ============================================================================
-- Fim da migration 037. O runner registra versao e checksum em
-- schema_migrations; nao e necessario INSERT manual aqui.
-- ============================================================================
