# Progresso 12 — Contrato Clínico para Prescrição Segura

## Data
2026-04-16

## Objetivo do bloco
1. Formalizar o contrato mínimo para cálculo seguro de dosagem
2. Tirar a tela de prescrição do payload ad hoc incompatível com o backend
3. Expor no frontend quais campos faltam para liberar o prescriber

## Trabalho realizado

### 1. Contrato clínico explícito

- criado `src/services/prescription_contract.py`
- o contrato passou a resolver, com trilha de origem:
  - `patient_name`
  - `age`
  - `main_complaint`
  - `symptoms`
  - `weight_kg`
  - `height_cm`
  - `prior_cannabis_use`
  - `conditions`
  - `current_medications`
  - `allergies`
  - `medical_history`
  - `risk_level`
- os campos mínimos para prescrição segura passaram a ser tratados como obrigatórios no contrato:
  - nome
  - idade
  - queixa principal
  - sintomas
  - peso
  - altura
  - uso prévio de cannabis

### 2. Backend de prescrição alinhado

- `src/services/prescription_service.py` agora aceita `attendance_id`
- o serviço monta o `DosageInput` a partir do atendimento salvo + overrides manuais
- se o contrato estiver incompleto, a rota retorna:
  - código `prescription_contract_incomplete`
  - detalhes estruturados do contrato
- `src/web/routes/api_v1.py` passou a incluir `prescription_contract` no detalhe do atendimento
- `src/web/routes/prescriptions.py` passou a expor esse erro estruturado

### 3. Frontend de prescrição corrigido

- `frontend/app/med/prescricao/[id]/page.tsx` deixou de mandar um payload incompatível com o backend para cálculo
- a tela agora:
  - lê `prescription_contract` do atendimento
  - mostra status `Pronto` vs `Pendente`
  - permite preencher manualmente `weight_kg`, `height_cm` e `prior_cannabis_use`
  - envia apenas os overrides mínimos + `attendance_id` para cálculo
  - usa a recomendação retornada para preencher melhor a UI
- a emissão formal passou a usar payload compatível com `PrescriptionPayload`:
  - `patient_id`
  - `doctor_user_id`
  - `doctor_name`
  - `doctor_crm`
  - `dosage_recommendation`
  - `custom_notes`
  - `validity_days`

### 4. Cobertura adicionada

- criados:
  - `tests/test_prescription_contract.py`
  - `tests/test_prescriptions.py`
- cenários cobertos:
  - contrato incompleto por falta de uso prévio
  - merge de overrides manuais
  - geração do `DosageInput`
  - retorno estruturado da rota de cálculo
  - payload de emissão formal

## Validações executadas

- `env\Scripts\python.exe -m pytest -q`
- `env\Scripts\python.exe -m py_compile src\services\prescription_contract.py src\services\prescription_service.py src\web\routes\prescriptions.py src\web\routes\api_v1.py`
- `npm exec tsc --noEmit` em `frontend/`
- `npm exec eslint app/med/prescricao/[id]/page.tsx lib/types.ts` em `frontend/`

## Estado após o bloco

### Fechado

- contrato mínimo para prescrição segura definido no código
- origem oficial de `weight_kg`, `height_cm` e `prior_cannabis_use` formalizada por contrato
- tela de prescrição alinhada ao backend para cálculo e emissão

### Ainda aberto

- coleta desses campos mais cedo no intake/triagem, e não apenas na tela de prescrição
- integração controlada do `AgentePrescritor` no fluxo clínico principal
- smoke real de emissão ponta a ponta com dados de atendimento reais no navegador
