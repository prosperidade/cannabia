# Documentação do Sistema CannabIA (Atualizada)

Este documento resume a arquitetura atual e aponta diferenças entre requisitos desejados e o que já está implementado.

## 1. Arquitetura atual

- **Entry point principal:** `src/app.py`
- **Rotas auxiliares em blueprints:**
  - `src/realtime_notifications.py`
  - `src/scheduling_chain.py`
  - `src/historico_atendimento.py`
- **Serviços:** `src/services/*`
- **Repositórios:** `src/repositories/*`
- **Infra existente:** `src/config.py`, `src/database.py`, `src/run_migrations.py`
- **Front-end server-side:** `src/templates/*` e `src/static/js/*`

## 2. Fluxo de execução

```text
Request -> Route/Blueprint -> Auth (quando protegido) -> Service -> Repository -> MySQL
```

## 3. Autenticação e autorização

### Implementado

- Flask-Login no app principal.
- `@login_required` em páginas protegidas (`/`, `/historico`, `/scheduling` e dashboard realtime).
- Login com credenciais vindas de `.env` (`APP_AUTH_USERNAME`, `APP_AUTH_PASSWORD`).

### Não implementado no estado atual

- tabela `users` para autenticação;
- `bcrypt` para hash de senha;
- roles `Admin`, `Medico`, `Atendente`;
- `@role_required`;
- `src/infra/security.py`.

## 4. Rotas existentes

- `/` (app principal + também rota do realtime blueprint)
- `/login`
- `/logout`
- `/webhook`
- `/scheduling`
- `/historico`
- `/dashboard` (em app separado `src/dashboard.py`)

Rotas solicitadas mas não implementadas no código atual:
- `/whoami`
- `/ai-audit`
- `/ai/test`
- prefixos `/realtime/*`, `/scheduling/*` e `/historico/*` (existem rotas simples sem subpath)

## 5. Auditoria de IA

Não existe hoje tabela `ai_audit_logs` nem mecanismo de persistência com campos como `total_tokens` e `estimated_cost_usd`.
Também não há trilha de status (`success`, `validation_error`, `security_blocked`, `error`) registrada para chamadas de IA.

## 6. Execução local

Consulte o `README.md` para checklist completo (venv, `.env` e execução com `python -m src.app`).
