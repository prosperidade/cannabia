# Progresso 13 - Intake/Triagem alimentando o contrato clinico

Data: 2026-04-16

## Objetivo

Empurrar a coleta de `weight_kg`, `height_cm` e `prior_cannabis_use` para a triagem/intake, em vez de depender apenas da tela de prescricoes.

## Entregas

- Triagem web ganhou passo inicial de identificacao com `patient_name` e `age`.
- Wizard de triagem agora envia payload real para `POST /api/v1/intake/triage`.
- Endpoint publico com CSRF grava intake em `anamnesis_reports`, usando `clinic_id` do contexto autenticado, do payload ou `DEFAULT_CLINIC_ID`.
- Novo service `src/services/triage_intake_service.py`:
  - normaliza o payload do wizard
  - monta `AnamnesisInput`
  - persiste `anamnesis_data` com `vital_signs.weight_kg`, `vital_signs.height_cm` e `prior_cannabis_use`
  - roda o fluxo clinico
  - cria evento de timeline
  - retorna `prescription_contract`
- A triagem agora gera atendimento clinico util para o medico, em vez de apenas estado local no frontend.

## Efeito pratico

- O medico passa a receber atendimentos oriundos da triagem web com os campos minimos do contrato clinico ja preenchidos no `anamnesis_data`.
- A tela de prescricao continua aceitando override manual, mas deixa de ser o unico ponto de coleta desses dados.

## Validacao

- `env\Scripts\python.exe -m pytest -q` -> `59 passed`
- `npm exec tsc --noEmit` -> ok
- `npm exec eslint app/triagem/page.tsx components/triagem/wizard-engine.tsx components/triagem/step-identificacao.tsx components/triagem/step-revisao.tsx lib/api.ts lib/types.ts lib/types-triagem.ts` -> ok
