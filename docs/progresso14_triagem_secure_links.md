# Progresso 14 - Triagem publica endurecida com link/token por clinica

Data: 2026-04-16

## Objetivo

Remover a dependencia de `clinic_id` aberto/default no intake web e trocar o acesso publico da triagem por link seguro emitido pela clinica.

## Entregas

- Novo service `src/services/triage_link_service.py` com token assinado para triagem.
- `POST /api/v1/intake/triage-link`:
  - autenticado
  - gera token por `clinic_id` do contexto
  - devolve URL pronta para compartilhar
- `GET /api/v1/intake/triage-link?token=...`:
  - publico
  - valida o token e resolve contexto da clinica
- `POST /api/v1/intake/triage`:
  - quando anonimo, exige `intake_token`
  - deixa de aceitar fallback publico por `clinic_id`/default
  - continua aceitando fluxo autenticado interno pela clinica ativa
- Frontend `/triagem`:
  - valida `?token=` antes de abrir o wizard
  - bloqueia acesso anonimo sem token
  - mostra estado de acesso protegido quando o link esta ausente ou invalido
- Cockpit medico:
  - [frontend/app/med/fila/page.tsx](/c:/Users/Administrador/Desktop/Cannabia/frontend/app/med/fila/page.tsx) ganhou acao para gerar e copiar link de triagem

## Configuracao

- Nova env: `TRIAGE_LINK_TTL_S`
  - default `259200` segundos
  - equivale a `72h`

## Validacao

- `env\Scripts\python.exe -m pytest -q` -> `64 passed`
- `npm exec tsc --noEmit` -> ok
- `npm exec eslint app/triagem/page.tsx app/med/fila/page.tsx app/page.tsx app/login/page.tsx components/triagem/wizard-engine.tsx lib/api.ts lib/types.ts` -> ok
