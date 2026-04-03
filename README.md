# CannabIA

Plataforma white-label multi-tenant para operação assistida no ecossistema de cannabis medicinal.

## Visão geral

A CannabIA não é apenas um sistema clínico para múltiplas clínicas. O produto documentado hoje é uma plataforma que combina:

- atendimento e acolhimento inicial
- anamnese assistida por IA
- preparação pré-consulta com apoio científico
- agenda e consulta
- acompanhamento longitudinal do paciente
- operação white-label por tenant
- governança de IA, integrações e auditoria

O repositório atual já possui uma base funcional importante, mas ainda está em transição do modelo centrado em `clinic_id` para o modelo amplo de `tenant`.

## Estado atual do repositório

Hoje a base implementada cobre principalmente:

- backend Flask modular
- autenticação com Flask-Login
- contexto multi-clínica por `clinic_id`
- webhook WhatsApp com persistência de mensagens
- fluxo conversacional de anamnese
- pipeline de IA com auditoria e cálculo de custo
- dashboard, histórico de mensagens, atendimentos e agendamento
- base inicial de conhecimento com ChromaDB

Os domínios ainda pendentes ou parciais incluem:

- tenancy amplo com `tenant_id`
- white-label completo por tenant
- prontuário longitudinal unificado
- acompanhamento semanal com questionários e escalonamento
- pagamentos e QR Code
- billing e monetização
- integração PubMed e governança formal de conhecimento

## Stack principal

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js App Router, React, TypeScript (bootstrap com dashboard, agenda e atendimentos) |
| Backend | Python 3.12, Flask 3.x, Flask-Login |
| App server | Gunicorn, Eventlet |
| Banco relacional | PostgreSQL, psycopg2 |
| IA | OpenAI GPT-4o-mini, Google Gemini |
| Embeddings | Google Gemini Embeddings |
| Vetorial | ChromaDB |
| Comunicação | WhatsApp Business API, SMTP |
| Validação | Pydantic v2 |
| Deploy | Render |

## Estrutura do projeto

```text
cannabia/
├── docs/
├── frontend/
├── migrations/
├── src/
│   ├── ai/
│   ├── infra/
│   ├── integrations/
│   ├── knowledge/
│   ├── repositories/
│   ├── services/
│   ├── templates/
│   ├── web/routes/
│   ├── app.py
│   ├── config.py
│   └── tenancy.py
├── tests/
├── create_admin.py
├── render.yaml
└── requirements.txt
```

## Documentação principal

Os documentos oficiais atuais estão em `docs/`:

| Documento | Papel |
|-----------|-------|
| `00_CURRENT_STATE_RESTRUCTURING_AND_ADAPTATION.md` | Contexto do estado atual e da adaptação |
| `01_PRODUCT_AND_BUSINESS_FOUNDATION.md` | Fundação de produto e negócio |
| `02_ECOSYSTEM_ENTITIES_AND_PERMISSIONS.md` | Entidades, perfis e permissões |
| `03_PATIENT_AND_DOCTOR_JOURNEYS.md` | Jornadas do paciente e do médico |
| `04_PATIENT_MONITORING_AND_ALERTS.md` | Acompanhamento e alertas |
| `05_WHITE_LABEL_AND_MONETIZATION_MODEL.md` | White-label e monetização |
| `06_AI_RAG_AND_KNOWLEDGE_ARCHITECTURE.md` | IA, RAG e conhecimento |
| `07_PLATFORM_ARCHITECTURE.md` | Arquitetura da plataforma |
| `08_DATABASE_AND_DOMAIN_MODEL.md` | Modelo de domínio e banco |
| `09_INTEGRATIONS_AND_EXTERNAL_SERVICES.md` | Integrações externas |
| `10_SECURITY_COMPLIANCE_AND_AUDIT.md` | Segurança, compliance e auditoria |
| `11_IMPLEMENTATION_GAP_ANALYSIS.md` | Gaps entre docs e sistema |
| `12_ADAPTATION_AND_REFACTORING_ROADMAP.md` | Roadmap macro |
| `13_MASTER_DOCUMENT_INDEX.md` | Índice mestre |
| `14_PHASE_1_CLOSURE_AND_READINESS.md` | Encerramento da fase documental |
| `15_SPRINT_1_EXECUTION_BACKLOG.md` | Backlog executável da sprint atual |
| `16_CURRENT_SYSTEM_INVENTORY.md` | Inventário técnico oficial da base atual |
| `17_TENANT_MIGRATION_PLAN.md` | Estratégia de transição de `clinic_id` para `tenant_id` |
| `18_SPRINT_2_BACKLOG.md` | Backlog da sprint focada em jornada, timeline e prontuário |
| `19_FRONTEND_STRATEGY.md` | Estratégia oficial de migração do frontend para Next.js |
| `20_FRONTEND_API_CONTRACT.md` | Contrato inicial de API entre Flask e o futuro frontend Next.js |

## Quick start local

### Pré-requisitos

- Python 3.12+
- PostgreSQL acessível via `DATABASE_URL`
- chaves de API da OpenAI e Google

### 1. Ambiente virtual e dependências

```bash
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
```

### 2. Variáveis de ambiente

Copie `.env.example` para `.env` e preencha, no mínimo:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
SECRET_KEY=...
FRONTEND_ORIGIN=http://localhost:3001,http://localhost:3000
```

### 3. Aplicar migrations atuais

No estado atual do repositório, o runner local aplica todas as migrations SQL em ordem:

```bash
python -m src.infra.run_migrations
```

### 4. Criar usuário administrador

```bash
python create_admin.py
```

### 5. Rodar a aplicação

```bash
python -m flask --app src.app run --debug
```

Aplicação local: `http://localhost:5000`

### 6. Rodar o frontend Next.js

```bash
cd frontend
copy .env.example .env.local
npm install
npm run dev
```

Frontend local: `http://localhost:3001`

O frontend novo usa um proxy same-origin em `/api/v1`, então ele não depende mais de expor
`NEXT_PUBLIC_API_BASE_URL` no navegador durante o desenvolvimento.

Rotas iniciais do frontend novo:

- `/dashboard`
- `/agendamentos`
- `/atendimentos`
- `/mensagens`
- `/auditoria-ia`

## Multi-tenancy atual

O isolamento efetivamente implementado hoje ainda é baseado em `clinic_id`.

- o contexto é resolvido em `src/tenancy.py`
- o vínculo usuário-clínica está em `user_clinics`
- os dados clínicos principais usam `clinic_id`

Essa é a base que será generalizada progressivamente para `tenant_id`, sem reconstrução total do sistema.

## Capacidades implementadas hoje

### Atendimento e comunicação

- webhook Meta para WhatsApp
- persistência de mensagens recebidas
- persistência de status de mensagens
- dashboard realtime básico

### Anamnese e IA

- máquina de estados conversacional para anamnese
- pipeline de 3 etapas com análise clínica, plano terapêutico e relatório científico
- fallback de relatório quando a base vetorial estiver vazia
- auditoria de execuções de IA no PostgreSQL

### Operação interna

- login e sessão
- dashboard com métricas operacionais básicas
- lista de atendimentos gerados pela anamnese
- agendamento simples
- histórico de mensagens

## Segurança atual

- senhas com hash bcrypt
- controle de sessão por Flask-Login
- CSRF nos formulários web
- rate limit básico em login e webhook
- validação contra prompt injection
- redaction parcial de dados sensíveis em logs

## Deploy

O projeto possui `render.yaml` para deploy no Render com:

- backend Flask
- frontend Next.js
- PostgreSQL gerenciado

## Convenção de trabalho

A partir de `2026-04-01`, o time mantém documentação operacional contínua em:

- `docs/runbook.md`
- `docs/progressoN.md`

Todo novo dia de trabalho deve gerar um novo arquivo de progresso seguindo o padrão definido no runbook.

## Observação importante

Se houver divergência entre o comportamento atual do código e descrições antigas do repositório, a fonte oficial de direção do produto passa a ser a série documental ativa em `docs/00` a `docs/19`.
