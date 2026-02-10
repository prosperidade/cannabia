# Documentação Completa do Sistema Cannab'IA

## 1) Visão Geral

O **Cannab'IA** é uma aplicação Flask para operação clínica e atendimento, com integração de:

- webhook de WhatsApp Cloud API;
- persistência em MySQL;
- dashboards web (realtime, histórico, agendamento e visão analítica);
- notificações externas (WhatsApp template + e-mail);
- módulos experimentais de IA clínica (LangChain/OpenAI).

Atualmente o projeto já possui base arquitetural em camadas e uma primeira entrega de segurança P0 (autenticação, RBAC, CSRF, hardening de webhook e redaction de logs).

---

## 2) Arquitetura Atual

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
   - `src/config.py`
   - `src/database.py`
   - `src/run_migrations.py`
   - `migrations/001_initial_schema.sql`
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
