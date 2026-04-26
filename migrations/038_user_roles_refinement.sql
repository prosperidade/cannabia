-- Migration 038: Refinamento de roles de usuario para o app unificado da clinica.
--
-- Contexto: a separacao "Atendente vs Medico vs Admin" estava sobreposta e
-- imprecisa. O app vai virar UM painel da clinica com sidebar dinamico por
-- role, e medico-dono precisa enxergar tanto a area clinica quanto a
-- administrativa sem trocar de login.
--
-- Mudancas desta migration:
--
--   1. ADD COLUMN users.is_clinic_admin BOOLEAN — flag combinavel com
--      qualquer role principal. Quando TRUE, o user enxerga as secoes
--      administrativas (Operacao, Configuracoes, DNA do Negocio,
--      Conformidade-gerir) alem das secoes do role principal.
--
--   2. Renomeacao de role 'Atendente' -> 'Recepcao' (ja em users.role).
--      O termo "Recepcao" descreve melhor o escopo: agenda, mensagens,
--      retornos, acompanhamento — sem acesso a financeiro nem admin.
--
--   3. Novos roles permitidos (whitelist passa a ser logica de aplicacao
--      pois `users.role` e VARCHAR(20) sem CHECK):
--        - Admin           (super admin global, /admin)
--        - Medico          (atendimento clinico)
--        - Recepcao        (operacao do dia, antes "Atendente")
--        - Financeiro      (estoque, faturamento, financeiro, campanhas)
--        - AdminClinica    (gestao da clinica/associacao, sem perfil clinico)
--        - Paciente        (portal paciente)
--
-- Idempotente:
--   - ADD COLUMN IF NOT EXISTS para is_clinic_admin
--   - UPDATE so atinge linhas com role='Atendente' (no-op em segundas
--     execucoes)
-- ============================================================================

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_clinic_admin BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN users.is_clinic_admin IS
    'TRUE quando o user e admin do tenant (combina com qualquer role: '
    'Medico+is_clinic_admin = medico-dono; AdminClinica+is_clinic_admin '
    'redundante mas valido). Quando TRUE, libera as secoes administrativas '
    'do app (Operacao, Configuracoes, DNA, Conformidade-gerir).';

-- Renomeacao Atendente -> Recepcao
UPDATE users SET role = 'Recepcao' WHERE role = 'Atendente';

-- Idem em user_clinics.role (vinculo do user ao tenant)
UPDATE user_clinics SET role = 'recepcao' WHERE role = 'atendente';
