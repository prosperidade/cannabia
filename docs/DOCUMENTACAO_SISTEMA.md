# Documentação Completa do Sistema Cannab'IA

## 1) Visão Geral

<<<<<<< HEAD
O projeto **Cannab'IA** é uma aplicação Flask com foco em atendimento e operação clínica, integrando:

- **Recebimento de eventos do WhatsApp** via webhook.
- **Persistência de mensagens e status** em MySQL.
- **Painéis web** para histórico, dashboard analítico e agendamento.
- **Automação de respostas** (template WhatsApp) e alerta crítico por e-mail.
- **Módulos experimentais com LangChain/OpenAI** para fluxos clínicos (anamnese, histórico, plano terapêutico, relatórios).

Atualmente o sistema está em uma fase de transição para arquitetura em camadas (`services`, `repositories`, `integrations`) com configuração centralizada.
=======
O **Cannab'IA** é uma aplicação Flask para operação clínica e atendimento, com integração de:

- webhook de WhatsApp Cloud API;
- persistência em MySQL;
- dashboards web (realtime, histórico, agendamento e visão analítica);
- notificações externas (WhatsApp template + e-mail);
- módulos experimentais de IA clínica (LangChain/OpenAI).

Atualmente o projeto já possui base arquitetural em camadas e uma primeira entrega de segurança P0 (autenticação, RBAC, CSRF, hardening de webhook e redaction de logs).
>>>>>>> 70cf1e7 (Documenta estratégia de reabertura de PR limpo para conflitos persistentes)

---

## 2) Arquitetura Atual

<<<<<<< HEAD
### 2.1 Camadas principais

1. **Camada de API/Rotas (Flask/Blueprints)**
   - `src/app.py`
   - `src/realtime_notifications.py`
   - `src/scheduling_chain.py`
   - `src/historico_atendimento.py`
   - `src/dashboard.py`
   - `src/webhook.py`

2. **Camada de Serviços (regras de negócio)**
   - `src/services/message_service.py`
   - `src/services/appointment_service.py`

3. **Camada de Repositórios (SQL)**
   - `src/repositories/message_repository.py`
   - `src/repositories/appointment_repository.py`

4. **Camada de Integrações externas**
   - `src/integrations/whatsapp.py`
   - `src/integrations/email.py`

5. **Infra/configuração**
=======
### 2.1 Camadas

1. **API/Entradas (Flask + Blueprints)**
   - `src/app.py` (app principal)
   - `src/realtime_notifications.py` (webhook + realtime)
   - `src/scheduling_chain.py` (agendamento)
   - `src/historico_atendimento.py` (histórico)
   - `src/dashboard.py` (analytics)
   - `src/webhook.py` (entrypoint alternativo minimal)

2. **Segurança transversal**
   - `src/auth.py` (login, RBAC, CSRF, rate-limit simples)
   - `src/security.py` (redaction de dados sensíveis)

3. **Serviços (regras de negócio)**
   - `src/services/message_service.py`
   - `src/services/appointment_service.py`

4. **Repositórios (SQL)**
   - `src/repositories/message_repository.py`
   - `src/repositories/appointment_repository.py`

5. **Integrações externas**
   - `src/integrations/whatsapp.py`
   - `src/integrations/email.py`

6. **Infra/Configuração**
>>>>>>> 70cf1e7 (Documenta estratégia de reabertura de PR limpo para conflitos persistentes)
   - `src/config.py`
   - `src/database.py`
   - `src/run_migrations.py`
   - `migrations/001_initial_schema.sql`
<<<<<<< HEAD

6. **Front-end (templates estáticos + JS)**
   - `src/templates/*.html`
   - `src/static/js/dashboard.js`

### 2.2 Fluxo principal (tempo real)

1. Meta/WhatsApp envia evento para `GET/POST /webhook` no blueprint de `realtime_notifications`.
2. `message_service` interpreta payload.
3. `message_repository` grava mensagem/status no MySQL.
4. Se necessário:
   - envia template via `integrations/whatsapp.py`;
   - envia alerta por e-mail via `integrations/email.py`.
5. Evento é emitido por Socket.IO para atualização no dashboard realtime.

---

## 3) Documentação de Arquivos (o que cada um faz)

## Raiz do projeto

- `.gitattributes`: define tratamento textual/binário para reduzir diffs ruins em PR.
- `requirements.txt`: dependências Python do projeto.
- `migrations/001_initial_schema.sql`: schema inicial para tabelas principais.
- `docs/DOCUMENTACAO_SISTEMA.md`: esta documentação.

## Pacote principal `src/`

### Arquivos de entrada e app

- `src/main.py`
  - Entry-point mínimo de teste (mensagem de ambiente).
- `src/app.py`
  - App Flask principal.
  - Registra blueprints de realtime, agendamento e histórico.
  - Inicializa Socket.IO e adiciona logging básico por request.
- `src/webhook.py`
  - App alternativo simplificado para subir apenas blueprint de webhook/realtime.

### Configuração e banco

- `src/config.py`
  - Carrega `.env` e expõe variáveis: DB, token webhook, SMTP, WhatsApp, secret key.
- `src/database.py`
  - Centraliza conexão MySQL (`get_connection`) e context manager (`db_cursor`).
- `src/run_migrations.py`
  - Runner simples para aplicar SQL do diretório `migrations`.

### API/rotas funcionais

- `src/realtime_notifications.py`
  - Blueprint `realtime_bp`.
  - Endpoint `/webhook` (GET verificação + POST eventos).
  - Endpoint `/` para template do dashboard em tempo real.
- `src/scheduling_chain.py`
  - Blueprint de agendamento (`/scheduling`) com formulário e listagem.
- `src/historico_atendimento.py`
  - Blueprint de histórico (`/historico`) de mensagens recebidas.
- `src/dashboard.py`
  - App de dashboard analítico (`/dashboard`) com agregações para gráficos.

### Camada de negócio (services)

- `src/services/message_service.py`
  - Parser de payload WhatsApp.
  - Regras de resposta automática por palavra-chave.
  - Regra de alerta crítico por e-mail.
  - Orquestra persistência de mensagem/status.
- `src/services/appointment_service.py`
  - Valida campos do formulário.
  - Converte data textual para formato SQL.
  - Chama repositório de agendamentos.

### Camada de dados (repositories)

- `src/repositories/message_repository.py`
  - Criação/garantia de tabelas de mensagens.
  - Inserção de mensagens e status.
  - Leitura e agregações para dashboard.
- `src/repositories/appointment_repository.py`
  - Criação/garantia da tabela `appointments`.
  - Inserção e listagem de agendamentos.

### Integrações externas

- `src/integrations/whatsapp.py`
  - Envio de template via WhatsApp Cloud API.
- `src/integrations/email.py`
  - Envio de e-mail SMTP (Gmail configurado por padrão).

### Templates e assets

- `src/templates/index.html`
  - Tela inicial com navegação.
- `src/templates/realtime_dashboard.html`
  - Dashboard em tempo real (Socket.IO + Chart.js).
- `src/templates/dashboard.html`
  - Dashboard analítico com filtro + gráficos + tabela.
- `src/templates/historico_atendimento.html`
  - Tabela de histórico de mensagens.
- `src/templates/scheduling_dashboard.html`
  - Form de agendamento + lista de consultas.
- `src/static/js/dashboard.js`
  - Script de dashboard (checar se está em uso real pelo template atual).

### Módulos legados / experimentais

> Esses arquivos coexistem com a arquitetura nova, mas parte deles usa padrão antigo (conexão SQL inline, execução isolada, duplicidade de integração).

- `src/create_tables.py`: cria tabelas legadas/auxiliares.
- `src/db_connect.py`: app antigo para dashboard (`/dashboard`) com acesso direto.
- `src/alerts_monitoring.py`: utilitário de inserção de alertas.
- `src/export.py` / `src/export_advanced.py`: exportação de dados/relatórios.
- `src/medical_history_chain.py`: pipeline LLM para histórico clínico.
- `src/anamnesis_chain.py`: pipeline LLM para anamnese.
- `src/treatment_plans_chain.py`: pipeline LLM para plano terapêutico.
- `src/reporting_chain.py`: pipeline LLM para relatórios.
- `src/whatsapp_message.py`: script one-shot para envio WhatsApp (legado).
- `src/whatsapp_template.py`: wrapper compatível para envio template.
- `src/whatsapp_utils.py`: utilitário legado duplicado de WhatsApp.
- `src/notifications.py`: wrapper compatível para notificação por e-mail.
- `src/send_whatsapp_template`: artefato sem extensão (revisar/remover se obsoleto).

### Pacotes vazios (marcadores)

- `src/__init__.py`
- `src/api/__init__.py`
- `src/services/__init__.py`
- `src/repositories/__init__.py`
- `src/integrations/__init__.py`

---

## 4) O que falta implementar para finalizar o projeto

## 4.1 Itens críticos (bloqueadores de produção)

1. **Instalação/ambiente reprodutível**
   - Padronizar setup (`venv`, `pip install -r requirements.txt`, `.env.example`).
   - Garantir encoding consistente do `requirements.txt` no repositório.

2. **Migração de schema real (sem CREATE TABLE em runtime)**
   - Remover `ensure_*_table()` das rotas/repositórios em produção.
   - Adotar ferramenta de migração robusta (Alembic) com versionamento incremental.

3. **Segurança de acesso web**
   - Implementar autenticação e autorização para `/dashboard`, `/historico`, `/scheduling`.
   - Proteção CSRF em formulários.
   - Hardening de sessão e segredo por ambiente.

4. **Observabilidade de verdade**
   - Logging estruturado com correlação por request.
   - Métricas (latência, taxa de erro, throughput) e healthcheck.
   - Alertas operacionais (falha webhook, falha DB, falha integração).

## 4.2 Itens de robustez técnica

1. **Unificação definitiva (remover legados duplicados)**
   - Consolidar tudo em uma única stack (manter arquitetura nova).
   - Remover módulos antigos que duplicam lógica (`db_connect.py`, `whatsapp_utils.py`, etc.).

2. **Modelagem e tipos de dados**
   - Corrigir coluna `timestamp` para tipo adequado (`DATETIME`/`BIGINT`) em tabela de mensagens.
   - Ajustar índices para consultas de dashboard (`sender`, `created_at`, `contact_name`).

3. **Qualidade de código e testes**
   - Testes unitários para services/repositories.
   - Testes de integração para webhook e blueprints.
   - Lint/format/CI (ruff/black/pytest em pipeline).

4. **Tratamento de erro e retry**
   - Retry/backoff para WhatsApp API e SMTP.
   - Dead-letter/log para falhas recorrentes.

## 4.3 Funcionalidades de produto pendentes

1. **Fila assíncrona**
   - Celery/RQ + Redis para envio de WhatsApp/email fora do request.

2. **Painel de SLA**
   - Tempo de resposta por remetente/equipe.
   - Indicadores de volume por período.

3. **Regras dinâmicas de auto-resposta**
   - CRUD de regras em banco (palavra-chave, template, prioridade, ativo/inativo).

4. **Gestão clínica completa**
   - Cadastro completo de pacientes (CRUD).
   - Prontuário/linha do tempo.
   - Plano terapêutico versionado.

5. **LGPD e auditoria**
   - Trilha de auditoria de ações.
   - Política de retenção e anonimização.

---

## 5) Plano sugerido de conclusão (roadmap curto)

## Sprint 1 (fundação)
- Congelar arquitetura nova e remover duplicidade legada.
- Implementar autenticação básica e healthcheck.
- Padronizar migrations e `.env.example`.

## Sprint 2 (confiabilidade)
- Fila assíncrona para integrações.
- Retry, circuit breaker e logs estruturados.
- Testes de integração do webhook.

## Sprint 3 (produto)
- SLA dashboard + regras dinâmicas de auto-resposta.
- CRUD de pacientes + prontuário.
- Auditoria e controles de LGPD.

---

## 6) Estado atual de prontidão

**Status geral:** protótipo avançado / pré-produção.

- Já possui fluxo funcional ponta a ponta (webhook → persistência → painel).
- Já iniciou separação arquitetural correta.
- Ainda faltam pilares de produção: segurança, migração madura, testes e operação observável.

Com os itens da seção 4 implementados, o projeto fica apto para operação estável em ambiente real.
=======
   - `.env.example`

7. **Frontend**
   - `src/templates/*.html`
   - `src/static/js/dashboard.js`

### 2.2 Fluxo principal (mensageria e realtime)

1. WhatsApp envia eventos para `POST /webhook`.
2. Endpoint valida limite/tamanho/schema básico.
3. `message_service` processa regra de negócio.
4. `message_repository` persiste evento/status.
5. Se aplicável: dispara integração de WhatsApp template/e-mail.
6. Evento redigido (`redact_dict`) é emitido por Socket.IO para painéis autenticados.

---

## 3) Segurança implementada (estado atual)

### 3.1 Já implementado (P0)

- Login e sessão com controle por papéis: `Admin`, `Medico`, `Atendente`.
- RBAC em rotas sensíveis:
  - `/dashboard`: Admin/Medico
  - `/historico`, `/scheduling`, `/realtime`: Admin/Medico/Atendente
- CSRF para login/logout/agendamento.
- Hardening de sessão:
  - `SESSION_COOKIE_SECURE`
  - `SESSION_COOKIE_HTTPONLY`
  - `SESSION_COOKIE_SAMESITE`
- Rate-limit em login e webhook (em memória, por IP/processo).
- Limite de tamanho de payload e validação básica de schema no webhook.
- Socket.IO bloqueado para sessão anônima.
- Redaction de logs/eventos para mascarar tokens/e-mails/telefones.
- Security headers básicos: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy.

### 3.2 Limitações conhecidas da implementação atual

- Rate-limit em memória não é distribuído (ideal: Redis).
- Usuários em `APP_USERS_JSON` (POC), ainda sem hash/salt em banco.
- Webhook ainda sem validação de assinatura criptográfica do provedor.
- Idempotência/replay ainda não persistida por `event_id/message_id`.

---

## 4) Mapa de arquivos (o que cada arquivo faz)

## 4.1 Raiz do projeto

- `.gitattributes`: normaliza tipos text/binário para diffs.
- `.env.example`: referência de variáveis de ambiente (sem segredos).
- `requirements.txt`: dependências Python.
- `migrations/001_initial_schema.sql`: schema inicial.
- `docs/DOCUMENTACAO_SISTEMA.md`: documento principal de arquitetura/produto.
- `docs/SECURITY_MODEL.md`: modelo de ameaça e controles de segurança.

## 4.2 `src/` — aplicação principal

### Entradas e aplicação
- `src/main.py`: entrypoint mínimo de ambiente.
- `src/app.py`: app principal, login/logout, segurança de sessão, headers, registro de blueprints e logging.
- `src/webhook.py`: entrypoint minimal para expor blueprint de realtime/webhook.

### Segurança
- `src/auth.py`: decorators `login_required`, `role_required`, CSRF e rate-limit simples.
- `src/security.py`: funções de redaction e formatter de log seguro.

### Configuração e banco
- `src/config.py`: leitura de `.env` + defaults operacionais.
- `src/database.py`: conexão MySQL e context manager `db_cursor`.
- `src/run_migrations.py`: aplica SQL da pasta `migrations`.

### API/Rotas
- `src/realtime_notifications.py`: webhook GET/POST, validação básica, emissão de eventos realtime.
- `src/scheduling_chain.py`: cadastro/listagem de consultas.
- `src/historico_atendimento.py`: exibição de mensagens históricas.
- `src/dashboard.py`: consultas agregadas para gráficos e listagem.

### Camadas de domínio
- `src/services/message_service.py`: parse de payload, auto-resposta e notificação crítica.
- `src/services/appointment_service.py`: validação e normalização de agendamento.
- `src/repositories/message_repository.py`: CRUD/aggregates de mensagens/status.
- `src/repositories/appointment_repository.py`: CRUD de agendamentos.

### Integrações
- `src/integrations/whatsapp.py`: cliente WhatsApp Cloud API.
- `src/integrations/email.py`: SMTP para alertas.
- `src/whatsapp_template.py`: wrapper de compatibilidade legado.
- `src/notifications.py`: wrapper legado de e-mail.

### Templates/UI
- `src/templates/login.html`: tela de autenticação.
- `src/templates/index.html`: home/navegação.
- `src/templates/realtime_dashboard.html`: painel socket em tempo real.
- `src/templates/dashboard.html`: analytics.
- `src/templates/historico_atendimento.html`: histórico tabular.
- `src/templates/scheduling_dashboard.html`: formulário + lista de consultas.
- `src/static/js/dashboard.js`: JS auxiliar (avaliar uso real).

### Módulos legados/experimentais
- `create_tables.py`, `db_connect.py`, `whatsapp_utils.py`, `whatsapp_message.py` e afins:
  coexistem por compatibilidade, mas não são o caminho arquitetural recomendado.
- `anamnesis_chain.py`, `medical_history_chain.py`, `treatment_plans_chain.py`, `reporting_chain.py`:
  experimentos com LLM e ainda sem grade completa de segurança PHI para produção.

---

## 5) O que falta para finalizar o projeto

## 5.1 Prioridade P0/P1 (produção com dados de saúde)

1. **Identidade e acesso (IAM) de produção**
   - Migrar usuários de `APP_USERS_JSON` para tabela de usuários com senha hash (`bcrypt/argon2`).
   - Implementar fluxo de reset, política de senha e MFA para perfis críticos.

2. **Webhook robusto**
   - Validar assinatura criptográfica oficial do provedor.
   - Idempotência persistida por `event_id/message_id` para bloquear replay.
   - Rate-limit distribuído via Redis.

3. **LGPD / PHI**
   - Criptografia de campos sensíveis em repouso (anamnese, relatórios, observações).
   - Chaves fora do banco (KMS/Secret Manager).
   - Política de retenção e anonimização.

4. **Operação segura**
   - Healthcheck, métricas e alertas (latência, erro webhook, falha SMTP/WhatsApp).
   - Logs estruturados com `request_id` e auditoria de acesso por paciente.

## 5.2 Qualidade e confiabilidade

1. **Testes automatizados**
   - Unitários para services/repositories/security.
   - Integração para login, CSRF, webhook, RBAC e socket auth.

2. **Banco e performance**
   - Mover completamente criação de schema para migrations versionadas.
   - Revisar tipo de `timestamp` (preferir `DATETIME/BIGINT` consistente).
   - Índices para consultas de dashboard.

3. **Fila assíncrona**
   - Mover envio de WhatsApp/e-mail para jobs (Celery/RQ + Redis), com retry e DLQ.

## 5.3 Produto clínico

- SLA de atendimento (tempo de resposta por contato/equipe).
- Regras dinâmicas de auto-resposta via painel.
- CRUD completo de paciente + prontuário + trilha de auditoria.

---

## 6) Roadmap sugerido (resumido)

### Sprint 1 (segurança e base)
- Usuários em banco com senha hash + migração de autenticação.
- Assinatura de webhook + idempotência persistida.
- Testes de segurança (RBAC/CSRF).

### Sprint 2 (confiabilidade)
- Rate-limit distribuído.
- Fila assíncrona para integrações.
- Métricas e alertas operacionais.

### Sprint 3 (produto)
- SLA dashboard.
- Regras dinâmicas de auto-resposta.
- Evolução do prontuário com LGPD/auditoria.

---

## 7) Status de prontidão

**Estado atual:** pré-produção fortalecida (com P0 inicial já implementado), porém ainda não pronta para operação plena com alto volume e requisitos regulatórios completos.

Para “go-live” com dados sensíveis, priorizar os itens das seções 5.1 e 5.2.


---

## 8) Histórico recente de entregas

- Reestruturação para arquitetura em camadas (`services`, `repositories`, `integrations`).
- Endurecimento inicial de segurança (RBAC, CSRF, hardening de sessão, webhook com rate-limit/validação, redaction).
- Atualização da documentação técnica e do modelo de ameaça para refletir o estado real do projeto.
>>>>>>> 70cf1e7 (Documenta estratégia de reabertura de PR limpo para conflitos persistentes)
