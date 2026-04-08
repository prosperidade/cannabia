# Runbook de Trabalho

## Início de vigência

2026-04-01

## Propósito

Este runbook define o padrão operacional mínimo de documentação contínua da CannabIA a partir de 2026-04-01.

O objetivo é manter um histórico simples, cumulativo e rastreável de:

- decisões
- progresso diário
- bloqueios
- próximos passos
- arquivos impactados

## Regra principal

Todo dia de trabalho deve gerar um novo arquivo de progresso na pasta `docs`, seguindo a sequência:

```text
progresso1.md
progresso2.md
progresso3.md
...
```

## Convenção obrigatória

- Cada arquivo `progressoN.md` representa um dia ou ciclo diário de trabalho
- A data deve ser registrada explicitamente dentro do arquivo
- Se houver mais de uma sessão no mesmo dia, o conteúdo deve ser acrescentado no mesmo arquivo do dia
- O próximo arquivo só deve ser aberto quando houver um novo dia de trabalho
- O conteúdo deve ser objetivo, rastreável e técnico

## Estrutura mínima de cada progresso diário

Cada arquivo `progressoN.md` deve conter, no mínimo:

```text
# Progresso N

## Data
## Objetivo do dia
## Trabalho realizado
## Decisões registradas
## Próximos passos
## Arquivos relevantes do dia
## Bloqueios
```

E deve encerrar com uma orientação explícita para a próxima sessão, mantendo uma missão inicial sugerida no final do arquivo.

## Regras de preenchimento

- Registrar o que realmente foi feito, sem texto genérico
- Listar decisões que afetam arquitetura, backlog, fluxo ou operação
- Informar bloqueios reais, se existirem
- Encerrar o arquivo com próximos passos claros
- Encerrar o arquivo com uma missão inicial sugerida para a próxima manhã ou próxima sessão
- Sempre citar arquivos importantes tocados ou criados no dia

## Quando atualizar o runbook

O `runbook.md` deve ser atualizado quando houver mudança em:

- convenção de nome dos arquivos diários
- estrutura mínima dos registros
- padrão de documentação do time
- regras de operação e handoff
- procedimentos operacionais técnicos (migrations, deploys, testes, criptografia)

## Padrão adotado a partir de hoje

Em 2026-04-01, fica definido que:

- a pasta oficial desses registros é `docs`
- o primeiro arquivo da sequência é `docs/progresso1.md`
- este `docs/runbook.md` passa a ser a referência operacional do padrão

---

## Procedimentos Técnicos Operacionais

### Migrations

O sistema usa migrations SQL sequenciais em `migrations/` com versionamento automático.

**Runner**: `src/infra/run_migrations.py`

**Tabela de controle**: `schema_migrations(version, filename, applied_at, checksum)`

**Comportamento**:
- Na execução, garante a existência de `schema_migrations` via `migrations/000_migration_tracking.sql`
- Lê todos os arquivos `*.sql` em `migrations/` exceto prefixo `000_`, ordenados por nome
- Para cada arquivo, extrai a versão do prefixo (ex: `007` de `007_add_foreign_keys.sql`)
- Se a versão já existe em `schema_migrations`: pula. Se checksum diverge: emite `WARNING`
- Se a versão não existe: executa o SQL, registra versão + checksum SHA-256

**Execução local**:
```bash
python -m src.infra.run_migrations
```

**Em deploy (Render)**: executado automaticamente via `preDeployCommand` no `render.yaml`

**Migration com FKs (007)**: executar em janela de manutenção se houver volume — faz `DELETE` de órfãos e `ALTER TABLE ADD CONSTRAINT` em transação

### Health Check

**Endpoint**: `GET /api/v1/health`

**Probes**: DB (`SELECT 1` via pool), OpenAI (models.list), Gemini (models.list), ChromaDB (collection.count)

**Status**:
- `healthy` (HTTP 200): todos os probes ok
- `degraded` (HTTP 200): DB ok, mas algum AI provider down
- `unhealthy` (HTTP 503): DB down

**Resposta JSON**:
```json
{
  "data": {
    "status": "healthy|degraded|unhealthy",
    "components": {
      "db": {"status": "ok", "latency_ms": 5, "detail": "pool: 1 used / 9 available"},
      "openai": {"status": "ok", "latency_ms": 150},
      "gemini": {"status": "ok", "latency_ms": 200},
      "chromadb": {"status": "ok", "latency_ms": 8, "detail": "42 chunks"}
    }
  }
}
```

**Usado pelo Render**: configurado como `healthCheckPath` no `render.yaml`

### Métricas de Latência

**Endpoint**: `GET /api/v1/admin/metrics` (requer role Admin)

**Métricas coletadas automaticamente**:
- `http.request`: latência total por request HTTP
- `http.endpoint.<nome>`: latência por endpoint Flask
- `ai.stage.clinical`: tempo do estágio 1 do pipeline de IA
- `ai.stage.treatment`: tempo do estágio 2
- `ai.stage.rag_lookup`: tempo da busca vetorial
- `ai.stage.report`: tempo do estágio 3 (relatório científico)

**Formato de resposta**: cada métrica retorna `{count, p50_ms, p95_ms, p99_ms}`

**Janela**: últimas 1000 amostras por métrica (sliding window in-process)

### Connection Pooling

**Módulo**: `src/infra/database.py`

**Pool**: `psycopg2.pool.SimpleConnectionPool` com lazy init

**Configuração via env vars**:
- `DB_POOL_MIN`: conexões mínimas (default 2)
- `DB_POOL_MAX`: conexões máximas (default 10)

**Uso**: toda operação de banco deve usar `db_cursor()` (context manager) — obtém do pool e devolve automaticamente. Nunca chamar `get_connection()` direto sem devolver via `release_connection()`.

**Monitoramento**: stats do pool visíveis no probe de DB do health check (`used`/`available`)

### Logging

**Formato**: JSON estruturado, uma linha por log record

**Campos padrão**: `timestamp`, `level`, `logger`, `module`, `message`

**Campos de contexto** (quando disponíveis): `request_id`, `user_id`, `tenant_id`, `clinic_id`, `path`, `method`, `status_code`, `elapsed_ms`

**Redação automática**: tokens Bearer, e-mails, telefones com 8+ dígitos

**Destinos**: stdout (console) + `cannabia.log` (arquivo)

**Correlação**: todo log dentro de um request HTTP carrega o mesmo `request_id` (UUID v4)

### Criptografia de Dados em Repouso

**Módulo**: `src/infra/crypto.py`

**Algoritmo**: Fernet (AES-128-CBC com HMAC-SHA256 via `cryptography` lib)

**Chave**:
- Variável de ambiente `ENCRYPTION_KEY` (prioridade)
- Fallback: derivação de `SECRET_KEY` via HKDF-SHA256 com salt `cannabia-fernet-v1`

**Gerar chave**:
```bash
python -c "from src.infra.crypto import generate_key; print(generate_key())"
```

**Uso**: `encrypt_value(plaintext) -> ciphertext` e `decrypt_value(ciphertext) -> plaintext`

**Colunas protegidas** (tabela `tenant_integrations`): `meta_whatsapp_key_encrypted`, `email_password_encrypted`, `ai_api_key_encrypted`

**Rotação de chave**: não suportada automaticamente. Alterar `ENCRYPTION_KEY` invalida todos os valores criptografados existentes. Procedimento: descriptografar com chave antiga, re-criptografar com nova.

### Trilha de Auditoria

**Tabela**: `audit_trail`

**Módulo**: `src/infra/audit.py` — `log_audit_event()`

**Eventos auditados**:
| Ação | Resource Type | Quando |
|------|--------------|--------|
| `login_success` | `session` | Login bem-sucedido via API |
| `login_failed` | `session` | Tentativa de login com credenciais inválidas |
| `logout` | `session` | Logout via API |
| `attendance_reviewed` | `anamnesis_report` | Médico revisa atendimento |
| `medical_record_saved` | `medical_record_entry` | Prontuário criado ou atualizado |

**Campos registrados**: `clinic_id`, `tenant_id`, `user_id`, `action`, `resource_type`, `resource_id`, `details` (JSONB), `ip_address`, `user_agent`, `created_at`

**Resiliência**: falhas de escrita na tabela de auditoria são logadas mas nunca interrompem a operação do usuário

### RBAC (Controle de Acesso Baseado em Permissões)

**Módulo**: `src/infra/permissions.py`

**Modelo**: permissões granulares no formato `recurso:ação`, mapeadas a roles

**Hierarquia**:
```
Atendente (8 perms):  session:*, dashboard:read, message:read, appointment:*, timeline:read
    ↓
Medico (13 perms):    + attendance:review, medical_record:*, ai:execute, ai:metrics_read
    ↓
Admin (16 perms):     + admin:metrics, admin:users, admin:tenants, admin:knowledge, admin:prompts, admin:audit
```

**Decorators disponíveis**:
- `@api_permission_required("attendance:read")` — semântica OR
- `@api_all_permissions_required("medical_record:write", "attendance:review")` — semântica AND

**Compatibilidade**: `api_role_required()` continua funcionando. Migração para `api_permission_required()` deve ser incremental por rota.

### Testes

**Framework**: pytest

**Execução**:
```bash
pip install -r requirements-dev.txt
pytest -v
pytest --cov=src --cov-report=term-missing
```

**Configuração**: `pytest.ini` (testpaths, addopts)

**Fixtures** (`tests/conftest.py`):
- `app`: Flask app em modo TESTING
- `client`: test client HTTP
- `authenticated_client`: client com sessão de admin
- `db_connection` / `db_cursor`: conexão com rollback automático por teste
- `mock_openai` / `mock_gemini`: mocks de provedores de IA
- `csrf_headers`: headers com CSRF token
- `sample_anamnesis_data`: payload de anamnese válido

**Banco de testes**: configurável via `TEST_DATABASE_URL` (default: `postgresql://localhost/cannabia_test`)

**Testes que não dependem de banco**: `test_crypto.py`, `test_permissions.py`, `test_metrics.py`

### Tenant Onboarding (B2B)

**Serviço**: `src/services/tenant_service.py`

**Blueprint**: `src/web/routes/tenant_admin.py` — prefixo `/api/v1/admin/tenants`

**Endpoints**:

| Método | Rota | Ação | Autenticação |
|--------|------|------|--------------|
| `POST` | `/api/v1/admin/tenants` | Cria tenant com provisão completa | Admin |
| `GET` | `/api/v1/admin/tenants` | Lista tenants (filtros: status, type, limit, offset) | Admin |
| `GET` | `/api/v1/admin/tenants/<id>` | Detalhes com branding e user_count | Admin |
| `PUT` | `/api/v1/admin/tenants/<id>` | Atualiza legal_name, display_name, status | Admin |
| `POST` | `/api/v1/admin/tenants/<id>/users` | Convida usuário com role | Admin |

**Fluxo de criação de tenant**:
1. Valida dados (legal_name, display_name obrigatórios)
2. Resolve `tenant_type_id` a partir do slug (clinic, association, doctor)
3. Gera slug URL-safe com unicidade incremental
4. Em transação atômica: insere `tenants` → insere `clinics` (espelho legado) → vincula → insere `tenant_branding` → insere `tenant_integrations`
5. Registra evento `tenant_created` em `audit_trail`

**Criar tenant via curl**:
```bash
curl -X POST http://localhost:5000/api/v1/admin/tenants \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>" \
  -d '{
    "legal_name": "Clínica São Lucas LTDA",
    "display_name": "Clínica São Lucas",
    "tenant_type": "clinic"
  }'
```

**Convidar usuário**:
```bash
curl -X POST http://localhost:5000/api/v1/admin/tenants/2/users \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>" \
  -d '{
    "username": "dr.silva",
    "password": "senha123segura",
    "role": "Medico"
  }'
```

### Motor de Campanhas Ativas

**Migration**: `migrations/011_campaign_templates.sql` — 3 tabelas

**Serviço**: `src/services/campaign_service.py`

**Blueprint**: `src/web/routes/campaigns.py` — prefixo `/api/v1/campaigns`

**Endpoints**:

| Método | Rota | Ação | Autenticação |
|--------|------|------|--------------|
| `POST` | `/api/v1/campaigns/templates` | Cria template | Admin/Medico |
| `GET` | `/api/v1/campaigns/templates` | Lista templates (filtros: status, channel) | Admin/Medico |
| `GET` | `/api/v1/campaigns/templates/<id>` | Detalhes do template | Admin/Medico |
| `PATCH` | `/api/v1/campaigns/templates/<id>/status` | Ativa/arquiva template | Admin/Medico |
| `POST` | `/api/v1/campaigns/templates/<id>/send` | Dispara campanha (202 Accepted) | Admin/Medico |
| `GET` | `/api/v1/campaigns/executions` | Lista execuções | Admin/Medico |
| `GET` | `/api/v1/campaigns/executions/<id>` | Status detalhado | Admin/Medico |

**Ciclo de vida de uma campanha**:
1. **Criar template** (`POST /templates`) — status `draft`, corpo com variáveis `{{patient_name}}`
2. **Ativar template** (`PATCH /templates/<id>/status` com `{"status": "active"}`)
3. **Disparar campanha** (`POST /templates/<id>/send`) — retorna 202 com `execution_id`
4. **Worker processa** — resolve recipients, interpola variáveis, envia por canal, rate-limit 5/s
5. **Consultar status** (`GET /executions/<id>`) — acompanha sent_count, failed_count, status

**Variáveis de template** (sintaxe Mustache):
- `{{patient_name}}` — nome do paciente
- `{{clinic_name}}` — nome do template/clínica
- Variáveis não resolvidas permanecem como `{{nome}}` no texto final

**Canais suportados**:
- `whatsapp` — via `send_whatsapp_text()` (janela de 24h do Meta)
- `email` — via `send_email_notification()` (SMTP)
- `sms` — reservado (`NotImplementedError`)

**Rate limit**: 5 mensagens por segundo por execução (configurável via `DEFAULT_RATE_LIMIT_PER_SECOND`)

**Task queue**: Redis/RQ (fila `campaigns`). Fallback síncrono se Redis indisponível.

**Aplicar migration 011**:
```bash
python -m src.infra.run_migrations
# Ou manualmente:
psql $DATABASE_URL -f migrations/011_campaign_templates.sql
```

**Testar ciclo completo**:
```bash
# 1. Criar template
curl -X POST http://localhost:5000/api/v1/campaigns/templates \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>" \
  -d '{
    "name": "Lembrete de Consulta",
    "template_body": "Olá {{patient_name}}, sua consulta está agendada. Não esqueça!",
    "channel": "whatsapp"
  }'

# 2. Ativar
curl -X PATCH http://localhost:5000/api/v1/campaigns/templates/1/status \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>" \
  -d '{"status": "active"}'

# 3. Disparar (202 Accepted)
curl -X POST http://localhost:5000/api/v1/campaigns/templates/1/send \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>"

# 4. Consultar status
curl http://localhost:5000/api/v1/campaigns/executions/1 \
  -H "Cookie: session=<cookie>"
```

**Iniciar worker de campanhas**:
```bash
rq worker campaigns --url $REDIS_URL
```

### Agente de Triagem (Widgets Mágicos)

**Módulos**: `src/ai/prompts.py` (system prompt), `src/ai/schemas.py` (schemas + tool defs), `src/ai/chains.py` (`run_triage_agent()`)

**Prompt Registry**: chave `triage_agent` — gerenciável via DB (`ai_prompt_versions`) com fallback hardcoded

**Providers suportados**: OpenAI (function_calling) e Gemini (response_schema), com failover bidirecional via circuit breaker

**Structured output enforcement**:
- OpenAI: `tools` + `tool_choice=required` → modelo obrigado a invocar `render_triage_widget`
- Gemini: `response_mime_type=application/json` + `response_schema` → modelo retorna JSON conforme schema
- Ambos: validação Pydantic (`TriageResponse`) pós-parse como última linha de defesa

**Widgets disponíveis** (enum `WidgetType`):

| Widget | Quando usar | Payload (`data`) |
|--------|------------|------------------|
| `PHYSICAL_DATA_SLIDER` | Coletar peso/altura | `{suggested_weight, suggested_height, bmi_estimate}` |
| `PAIN_SCALE` | Paciente relata dor | `{suggested_level, body_region}` |
| `SYMPTOM_CHECKLIST` | Múltiplos sintomas | `{suggested_symptoms: [...]}` |
| `MEDICATION_SELECTOR` | Medicamentos mencionados | `{suggested_medications: [...]}` |
| `ALLERGY_TAGS` | Coletar/confirmar alergias | `{suggested_allergies: [...]}` |
| `VITAL_SIGNS` | Quadro exige sinais vitais | `{suggested_bp_systolic, suggested_bp_diastolic, suggested_heart_rate}` |
| `DOSAGE_CALCULATOR` | Dados suficientes para dosagem | `{cannabinoid_ratio, suggested_mg}` |
| `DOCUMENT_UPLOAD` | Precisa de exames/laudos | `{requested_documents: [...]}` |
| `APPOINTMENT_SCHEDULER` | Urgência/red flags | `{reason, urgency}` |
| `TEXT_ONLY` | Saudação/esclarecimento | `{}` |

**Env vars configuráveis**:
- `TRIAGE_MODEL_OPENAI`: modelo OpenAI (default `gpt-4o-mini`)
- `TRIAGE_MODEL_GEMINI`: modelo Gemini (default `gemini-1.5-flash`)

**Formato de resposta**:
```json
{
  "message": "Texto empático para o paciente (máx 3 frases)",
  "inject_widget": "PAIN_SCALE",
  "data": {"suggested_level": 6, "body_region": "lombar"},
  "extracted_conditions": [
    {
      "condition_name": "Lombalgia crônica",
      "icd10_hint": "M54.5",
      "confidence": "alto",
      "evidence_snippet": "dor nas costas há 3 meses"
    }
  ],
  "follow_up_question": "Essa dor irradia para as pernas?"
}
```

**Uso programático**:
```python
from src.ai.chains import run_triage_agent

response, tokens = run_triage_agent(
    patient_message="Tenho sentido muita dor nas costas há 3 meses...",
    patient_name="Maria",
    age=45,
    clinic_id="clinic_abc",
    prior_context="Primeira consulta.",
    provider="openai",  # ou "gemini"
)

# response.inject_widget → WidgetType.PAIN_SCALE
# response.data → {"suggested_level": 6, "body_region": "lombar"}
# response.extracted_conditions → [ExtractedCondition(...)]
```

**Frontend**: consome `inject_widget` como chave de roteamento para renderizar o Nano-App correspondente, e `data` como props do componente.

### Chat Dinâmico — WebSocket de Intake (Fase 5.6)

**Módulos**: `src/services/chat_session_service.py`, `src/web/routes/chat_intake.py`

**Namespaces SocketIO**:
- `/chat` — pacientes preenchendo intake (sem login Flask, autenticado por session_id)
- `/chat-monitor` — staff da clínica acompanhando intakes (requer login Flask)

**Endpoints REST**:

| Método | Rota | Auth | Uso |
|--------|------|------|-----|
| `POST` | `/api/v1/chat/sessions` | Login + clinic_id | Cria sessão, retorna `patient_token` |
| `POST` | `/api/v1/chat/handshake` | Token (sem login) | Troca `patient_token` por `session_id` + `ws_path` |
| `GET` | `/api/v1/chat/sessions/<id>` | Login + clinic_id | Status da sessão |
| `GET` | `/api/v1/chat/metrics` | Login | Contagem de sessões ativas |

**Fluxo completo de intake**:
```
1. Clínica: POST /api/v1/chat/sessions → {patient_token}
2. Envia link ao paciente com patient_token
3. Paciente: POST /api/v1/chat/handshake {token} → {session_id, ws_path: "/chat"}
4. Paciente: abre WebSocket em /chat, emite join_session({session_id})
5. Paciente: emite step_data({session_id, step, value}) por cada campo
6. Paciente: emite complete({session_id}) ao finalizar
7. Staff: conecta em /chat-monitor, emite watch_clinic → recebe patient_progress
```

**Configuração via env vars**:

| Variável | Default | Descrição |
|----------|---------|-----------|
| `CHAT_SESSION_TTL_S` | `3600` | TTL de sessões de intake (1h) |
| `CHAT_CLEANUP_INTERVAL_S` | `300` | Intervalo de limpeza de expiradas (5min) |

**Campos cifrados automaticamente** (Fernet via `crypto.py`):
`cpf`, `rg`, `phone`, `email`, `address`, `medication_details`, `diagnosis_history`

**Store**: in-memory com `threading.Lock`. Dados perdidos em restart. Migrar para Redis ao escalar multi-worker.

**Testar handshake + WS localmente**:
```bash
# 1. Criar sessão (requer login)
curl -X POST http://localhost:5000/api/v1/chat/sessions \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<cookie>" \
  -d '{"patient_name": "João Silva", "patient_phone": "5511999990000"}'

# 2. Handshake (sem login, com token do response anterior)
curl -X POST http://localhost:5000/api/v1/chat/handshake \
  -H "Content-Type: application/json" \
  -d '{"token": "<patient_token_do_passo_1>"}'

# 3. Conectar WebSocket (via Python)
python -c "
import socketio
sio = socketio.Client()
sio.connect('http://localhost:5000', namespaces=['/chat'])
sio.emit('join_session', {'session_id': '<session_id>'}, namespace='/chat')

@sio.on('session_joined', namespace='/chat')
def on_joined(data):
    print('Joined:', data)
    sio.emit('step_data', {
        'session_id': data['session_id'],
        'step': 'patient_name',
        'value': 'João Silva'
    }, namespace='/chat')

@sio.on('step_ack', namespace='/chat')
def on_ack(data):
    print('Ack:', data)
    sio.emit('complete', {'session_id': '<session_id>'}, namespace='/chat')

@sio.on('intake_complete', namespace='/chat')
def on_complete(data):
    print('Complete:', data)
    sio.disconnect()

sio.wait()
"

# 4. Verificar métricas
curl http://localhost:5000/api/v1/chat/metrics -H "Cookie: session=<cookie>"
```

**Troubleshooting — Chat WebSocket**:

| Sintoma | Causa provável | Ação |
|---------|---------------|------|
| Handshake retorna 404 | Token expirado ou inválido | Criar nova sessão e reenviar link |
| Handshake retorna 410 | Sessão já completada | Criar nova sessão |
| WS disconnect após `join_session` | session_id inválido ou expirado | Verificar TTL; repetir handshake |
| `step_ack` com `encrypted: true` | Campo na lista `_SENSITIVE_FIELDS` | Esperado — dado cifrado no store |
| `patient_progress` com `last_step` ilegível | Step sensível cifrado na telemetria | Esperado — descriptografado no `intake_submitted` final |
| Sessões não expirando | Cleanup lazy a cada `CHAT_CLEANUP_INTERVAL_S` | Aguardar próximo ciclo ou restart |
| `error: "Sessão inválida."` no WS | Socket operando em sessão de outro sid | Reconectar e re-emitir `join_session` |

### Setup Local Completo (Novo — 2026-04-07)

**Script**: `scripts/setup_local.py`

**Pré-requisitos**: PostgreSQL local rodando, DATABASE_URL no `.env` apontando para `localhost:5432/cannabia`

**Execução**:
```bash
cd c:\Users\Administrador\Desktop\Cannabia
env\Scripts\activate
python scripts/setup_local.py
```

**O que faz**:
1. Roda todas as migrations (000-013) via `src/infra/run_migrations.py`
2. Cria usuarios base via `scripts/seed_users.py` (admin, medico, atendente, paciente)
3. Popula dados demo via `scripts/seed_comprehensive.py` (~200 registros)

**Usuarios de teste**:

| Login | Senha | Role | Painel |
|-------|-------|------|--------|
| `admin` | `admin123` | Admin | `/admin` |
| `medico` | `medico123` | Medico | `/med/dashboard` |
| `atendente` | `atendente123` | Atendente | `/org/dashboard` |
| `paciente` | `paciente123` | Paciente | `/p/dashboard` |

**Iniciar sistema**:
```bash
# Terminal 1 — Backend
python -m src.app
# Roda em http://127.0.0.1:5000

# Terminal 2 — Frontend
cd frontend && npm run dev
# Roda em http://127.0.0.1:3001
```

### Frontend — Stack e Rotas (Novo — 2026-04-07)

**Stack**: Next.js 16.2.2 + React 19 + TypeScript + Tailwind CSS v3 (Material Design 3 dark theme)

**Design System**:
- Cores: primary=#bee654, surface=#0e1606, error=#ffb4ab (40+ tokens MD3)
- Fontes: Manrope (headlines), Inter (body), Material Symbols Outlined (icones)
- Efeitos: glass-panel (glassmorphism com backdrop-blur)
- Componentes: 12 primitivos em `components/ui-tw/`
- Layouts: SidebarLayout (desktop), MobileLayout (mobile), WizardLayout (triagem)

**Rotas por persona (48 total)**:

| Persona | Base | Rotas | Layout |
|---------|------|-------|--------|
| Paciente | `/p/*` + `/triagem` | 5 paginas | MobileLayout |
| Medico | `/med/*` | 13 paginas | SidebarLayout |
| Organizacao | `/org/*` | 12 paginas | SidebarLayout |
| Admin | `/admin/*` | 4 paginas | SidebarLayout |
| Sistema | `/`, `/login`, `/settings` + redirects | 9 paginas | Standalone |

**Proxy API**: `/api/v1/[...path]` repassa para Flask backend em `BACKEND_ORIGIN` (default `http://127.0.0.1:5000`)

### Migration 013 — Tabelas e Colunas Faltantes (Novo — 2026-04-07)

**Arquivo**: `migrations/013_missing_tables_and_columns.sql`

**Tabelas criadas**:
- `symptom_diary` — diario de sintomas do paciente
- `stock_inventory` — estoque de produtos canabicos
- `stock_dispensations` — dispensacao ao paciente
- `billing` — faturamento clinico simples

**Colunas adicionadas**:
- `patients.user_id` — link paciente ↔ usuario
- `patients.status` — status do paciente (ativo, em_tratamento, etc.)
- `treatment_plans.*` — 11 colunas clinicas (plan_name, cbd_thc_ratio, dosage, etc.)

**View criada**:
- `clinic_members` — alias para `user_clinics` (resolve referencia em org_management.py)

### Novos Endpoints Backend (2026-04-07)

**`src/web/routes/patient_portal.py`** — Blueprint `/api/v1/patient`:

| Método | Rota | Descricao |
|--------|------|-----------|
| GET | `/patient/profile` | Perfil do paciente logado |
| GET | `/patient/treatment` | Plano terapeutico ativo |
| POST | `/patient/diary` | Registrar entrada no diario |
| GET | `/patient/diary` | Historico do diario |
| GET | `/patient/evolution` | Metricas de evolucao |

**`src/web/routes/returns.py`** — Blueprint `/api/v1`:

| Método | Rota | Descricao |
|--------|------|-----------|
| GET | `/returns` | Pacientes para retorno/ajuste |

**`src/web/routes/org_management.py`** — Blueprint `/api/v1/org`:

| Método | Rota | Descricao |
|--------|------|-----------|
| GET | `/org/dashboard` | KPIs organizacionais |
| GET | `/org/patients` | Lista de pacientes |
| GET | `/org/doctors` | Lista de medicos |
| GET | `/org/stock` | Estoque |
| POST | `/org/stock/entry` | Entrada de estoque |
| POST | `/org/stock/dispensation` | Dispensacao |
| GET | `/org/billing` | Faturamento |
| GET | `/org/financial` | Financeiro |

---

## Observação final

Este runbook é um documento vivo. Ele deve permanecer curto, prático e útil para a execução diária.
