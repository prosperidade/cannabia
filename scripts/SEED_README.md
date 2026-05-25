# Seeds de desenvolvimento

Scripts para popular o banco local com dados sintéticos. Pré-requisito: stack
local rodando (`docker start cannabia-postgis`) e `migrations` aplicadas.

## Ordem de execução recomendada

```bash
# 1. Cria users dev refinados (admin/medico/dono/recepcao/financeiro/admin_clinica/paciente) + clinic 1
env/Scripts/python.exe scripts/seed_users.py

# 2. Popula a base clínica (15 patients, prescriptions, treatment plans,
#    appointments, symptom diary, medical records, etc.)
env/Scripts/python.exe scripts/seed_comprehensive.py

# 3. Popula o stack SCC (governance, members, sandbox, pharmacovigilance)
env/Scripts/python.exe scripts/seed_scc.py
```

Todos os seeds são **idempotentes** — pode rodar 2x sem duplicar dados.

## O que cada seed cria

### `seed_users.py`
- Clinic id=1 ("Clínica Cannabia")
- Users dev: `admin/admin123`, `medico/medico123`, `dono/dono123`,
  `recepcao/recepcao123`, `financeiro/financeiro123`,
  `admin_clinica/adminclinica123`, `paciente/paciente123`
- Vínculos `user_clinics` (membership) para cada user

### `seed_comprehensive.py` (~1730 linhas)
- 5 users adicionais (medico2, medico3, etc.)
- 15 patients realistas
- 8 anamnesis_reports
- Appointments, incoming messages
- Treatment plans + prescriptions
- Campaign templates, stock inventory + dispensations, billing
- 90 dias de symptom_diary para alguns patients
- AI audit logs, timeline events
- Medical records + entries
- Billing subscription

### `seed_scc.py` (~430 linhas — complementar SCC)
Cobre o que `seed_comprehensive` não toca (tabelas SCC criadas
em migrations 023-037).

**1. Governance Hub (F1):**
- 1 linha em `associations` (tenant_id=1, sandbox_application_status='preparing')
- 3 `institutional_documents` (estatuto, ata, comprovante CNPJ)
- 2 `technical_responsibles` (CRM + CRF)

**2. Association Members (F2):**
- 5 `association_members` vinculando os primeiros 5 patients ao tenant=1
- `associations.members_count` atualizado automaticamente

**3. Sandbox Defaults (F6.3):**
- Invoca `seed_sandbox_defaults(1)` (função SQL da migration 037)
- 10 `sanitary_risks` + 10 `sops` catalogados

**4. Sandbox Project + Protocol + Indicators + Values (F3.2):**
- 1 projeto `PROJ-SEED-001` (status=active, ANVISA-SANDBOX-2026-001)
- 1 `sandbox_protocol` v1.0 vigente (effective_until=NULL)
- 3 indicadores mandatórios:
  - `IDX-PAIN-REDUCTION` (target=3.0)
  - `IDX-RESPONSE-RATE` (target=0.7)
  - `IDX-AE-INCIDENCE` (target=0.05)
- 9 `sandbox_indicator_values` (3 períodos × 3 indicadores) — 3 deles
  on_target=True (M-1 caem na tolerância 5% da view)

**5. Pharmacovigilance (F3.1, F3.3+):**
- 6 `adverse_events` (description prefixada com `[SEED]`):
  - 3 mild, 1 moderate, 2 severe
  - 2 com `ai_triage_result` JSONB persistido (escalados via skill heurística)
  - Vinculados aos members da seção 2
- 2 `pharmacovigilance_notifications` (target=internal_only, mock)

## Estado esperado após rodar todos

Counts no `tenant_id=1`:

| Tabela | Esperado |
|---|---|
| tenants | 1 |
| clinics | 1 |
| users | 8 (4 base + 4 extras do comprehensive) |
| patients | 15 |
| association_members | 5 |
| institutional_documents | 3 |
| technical_responsibles | 2 |
| sanitary_risks | 10 |
| sops | 10 |
| sandbox_projects | 1 |
| sandbox_indicators | 3 |
| sandbox_indicator_values | 9 |
| adverse_events | 6 |
| pharmacovigilance_notifications | 2 |
| medical_records | 5 |
| symptom_diary | ~90 |
| treatment_plans | ~5 |
| prescriptions | ~5 |

## Como limpar (rollback)

Não há script automático de cleanup — para zerar o tenant 1, o caminho mais
seguro é dropar e recriar o DB:

```bash
docker exec cannabia-postgis psql -U postgres -c "DROP DATABASE cannabia;"
docker exec cannabia-postgis psql -U postgres -c "CREATE DATABASE cannabia;"
env/Scripts/python.exe scripts/run_migrations.py
# rodar os 3 seeds de novo
```

Para apagar **só o que o `seed_scc.py` criou** (preservando o resto):

```sql
-- Em ordem de FK reversa
DELETE FROM pharmacovigilance_notifications
  WHERE adverse_event_id IN (SELECT id FROM adverse_events WHERE description LIKE '[SEED]%');
DELETE FROM adverse_events WHERE description LIKE '[SEED]%';
DELETE FROM sandbox_indicator_values
  WHERE calculation_details->>'method' = 'seed_synthetic';
DELETE FROM sandbox_indicators
  WHERE indicator_code IN ('IDX-PAIN-REDUCTION', 'IDX-RESPONSE-RATE', 'IDX-AE-INCIDENCE');
DELETE FROM sandbox_protocols WHERE project_id IN
  (SELECT id FROM sandbox_projects WHERE project_code = 'PROJ-SEED-001');
DELETE FROM sandbox_projects WHERE project_code = 'PROJ-SEED-001';
DELETE FROM technical_responsibles
  WHERE professional_council = 'CRM' AND council_number = '12345' AND council_state = 'SP';
DELETE FROM technical_responsibles
  WHERE professional_council = 'CRF' AND council_number = '8721' AND council_state = 'SP';
DELETE FROM association_members
  WHERE membership_number IN ('MB-2026-0001','MB-2026-0002','MB-2026-0003','MB-2026-0004','MB-2026-0005');
DELETE FROM institutional_documents WHERE file_uri LIKE '/storage/seed/%';
-- sanitary_risks/sops do seed_sandbox_defaults têm risk_code/code próprios:
DELETE FROM sanitary_risks WHERE tenant_id = 1
  AND risk_code IN ('RISK-CONT-001','RISK-CONT-002','RISK-DOSE-001','RISK-DOSE-002',
                    'RISK-INTER-001','RISK-PV-001','RISK-TRACE-001',
                    'RISK-DATA-001','RISK-SUPPL-001','RISK-LEGAL-001');
DELETE FROM sops WHERE tenant_id = 1
  AND code IN ('SOP-CULT-001','SOP-CULT-002','SOP-EXT-001',
               'SOP-QC-001','SOP-QC-002','SOP-DISP-001',
               'SOP-PV-001','SOP-PV-002','SOP-GOV-001','SOP-GOV-002');
```

## Próximas camadas (não implementadas)

Estas são extensões úteis se a UI precisar de mais cenários:

- **Camada 4 — Anchoring:** popular `blockchain_anchors` com merkle roots
  fictícios e proof_uri, exercitando a UI da F5.
- **Camada 5 — Regulatory submissions/reports:** popular
  `regulatory_submissions` e `regulatory_reports` (7 tipos) para exercitar
  o blueprint `regulatory_reporting.py`.
- **Camada 6 — Document review workflows:** popular
  `document_review_workflows` para exercitar o pipeline F4.7.

Adicionar conforme demanda surgir.
