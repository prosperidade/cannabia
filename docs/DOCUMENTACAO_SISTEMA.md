# Documentação Completa do Sistema Cannab'IA

## 1) Visão Geral

O projeto **Cannab'IA** é uma aplicação Flask com foco em atendimento e operação clínica, integrando:

- **Recebimento de eventos do WhatsApp** via webhook.
- **Persistência de mensagens e status** em MySQL.
- **Painéis web** para histórico, dashboard analítico e agendamento.
- **Automação de respostas** (template WhatsApp) e alerta crítico por e-mail.
- **Módulos experimentais com LangChain/OpenAI** para fluxos clínicos (anamnese, histórico, plano terapêutico, relatórios).

Atualmente o sistema está em uma fase de transição para arquitetura em camadas (`services`, `repositories`, `integrations`) com configuração centralizada.

---

## 2) Arquitetura Atual

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
   - `src/config.py`
   - `src/database.py`
   - `src/run_migrations.py`
   - `migrations/001_initial_schema.sql`

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
