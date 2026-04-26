-- Down migration 038 — reverte refinamento de roles.
--
-- Restaura nomenclatura "Atendente" e remove a coluna is_clinic_admin.
-- Atencao: usuarios criados depois com role='Financeiro' ou 'AdminClinica'
-- ficam com role invalido apos rollback (esses roles nao existiam antes
-- da 038). O rollback so devolve "Atendente".
-- ============================================================================

-- Reverter renomeacao Atendente
UPDATE users         SET role = 'Atendente' WHERE role = 'Recepcao';
UPDATE user_clinics  SET role = 'atendente' WHERE role = 'recepcao';

-- Drop da flag is_clinic_admin
ALTER TABLE users DROP COLUMN IF EXISTS is_clinic_admin;
