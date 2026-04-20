# Progresso 16 — Sprints 6, 7 e 8 (Multi-tenancy, Financeiro, Hardening)

Data: 2026-04-17

## Contexto

Fechamento das tres ultimas sprints planejadas no progresso15: multi-tenancy
com white-label, dominio financeiro (Pix/QR + conciliacao) e hardening de
qualidade/seguranca.

---

## Sprint 6 — Multi-tenancy e white-label (entregas 2026-04-17)

### Migration 020 — tenant_extensions
- `migrations/020_tenant_extensions.sql`
- `tenants`: novas colunas `billing_plan`, `ai_executions_month`, `ai_limit_month`, `user_limit`, `quota_reset_at`
- `tenant_branding.subdomain`: indice unico case-insensitive
- `tenant_integrations`: `whatsapp_app_secret_encrypted`, `verify_token_encrypted`, `openai_api_key_encrypted`, `doctor_email`
- Indice `idx_tenants_slug_lower`

### Backend
- `src/repositories/tenant_settings_repository.py` (novo):
  - `get_branding`, `upsert_branding`, `resolve_tenant_by_subdomain`
  - `get_integrations(decrypted=True|False)`, `upsert_integrations` com criptografia Fernet
  - `get_tenant_quota`, `update_tenant_plan`, `increment_ai_usage`
- `src/services/tenant_secrets.py` (novo): resolve credenciais com fallback para env
  - `get_whatsapp_config(tenant_id)`, `get_email_config(tenant_id)`, `get_ai_config(tenant_id)`
- `src/tenancy.py`: extracao de subdominio do Host header e anexo de branding em `g.tenant_branding`
- `src/web/routes/tenant_admin.py`: novos endpoints
  - `GET/PUT /api/v1/admin/tenants/<id>/branding`
  - `GET/PUT /api/v1/admin/tenants/<id>/integrations` (secrets mascarados na leitura)
  - `GET/PUT /api/v1/admin/tenants/<id>/plan`
- `src/services/tenant_service.list_tenants`: agora retorna `plan`, `clinic_count`, `user_count`, `ai_executions_month`, `ai_limit_month`, `user_limit`
- `src/integrations/whatsapp.py` e `src/integrations/email.py`: aceitam `tenant_id` com fallback gracioso para env

### Frontend
- `frontend/lib/types-admin.ts`: `TenantBranding`, `TenantIntegrations`, `TenantPlanData`
- `frontend/lib/api.ts`: `getTenant`, `updateTenant`, `getTenantBranding`, `updateTenantBranding`, `getTenantIntegrations`, `updateTenantIntegrations`, `getTenantPlan`, `updateTenantPlan`
- `frontend/app/admin/tenants/[id]/page.tsx` (novo): abas Visao geral / Branding / Integracoes / Plano
  - Branding: nome, logo, subdominio, cores
  - Integracoes: 3 secoes (WhatsApp, E-mail/SMTP, Provedor IA) com campos tipo "password" que preservam segredos existentes quando deixados em branco
  - Plano: billing_plan, ai_limit_month, user_limit
- `frontend/app/admin/tenants/page.tsx`: modal "Nova Organizacao" agora chama a API; botao "Detalhes" navega para pagina por id

---

## Sprint 7 — Financeiro (entregas 2026-04-17)

### Migration 021 — payment_requests, payment_transactions, payment_webhook_log
- `migrations/021_payment_requests_transactions.sql`
- `payment_requests`: cobrancas (pix/boleto/cartao) com external_id, amount_cents, status, provider, pix_payload, expires_at
- `payment_transactions`: movimentos financeiros vindos de webhooks; idempotente via (provider, provider_event_id)
- `payment_webhook_log`: auditoria completa dos webhooks recebidos

### Backend
- `src/integrations/pix.py` (novo): gerador do BR Code EMV Pix (copia e cola) com CRC16-CCITT
- `src/repositories/payment_repository.py` (novo): CRUD de cobrancas, transacoes, webhook log, agregacoes por status
- `src/services/payment_service.py` (novo):
  - `issue_pix_charge` — emite Pix manual com chave configuravel por tenant
  - `confirm_payment` — marca como paga e registra transacao
  - `cancel_payment`, `list_payments`, `get_payment_detail`, `tenant_totals`
  - `process_webhook_event` — reconciliacao automatica idempotente
- `src/web/routes/payments.py` (novo):
  - `GET /payments`, `GET /payments/summary`, `GET /payments/<id>`
  - `POST /payments/pix` (emite cobranca) com CSRF
  - `POST /payments/<id>/confirm` e `POST /payments/<id>/cancel` com CSRF
  - `POST /payments/webhook/<provider>` publico (validado por HMAC)
- `src/tenancy.py`: `/api/v1/payments/webhook` adicionado a `PUBLIC_PREFIXES`

### Frontend
- `frontend/lib/types.ts`: `PaymentRequest`, `PaymentTransaction`, `PaymentDetail`, `PaymentSummary`
- `frontend/lib/api.ts`: `listPayments`, `getPaymentSummary`, `getPaymentDetail`, `issuePixCharge`, `confirmPaymentManual`, `cancelPayment`
- `frontend/app/org/pagamentos/page.tsx` (novo):
  - StatCards (pendentes, recebidos, cancelados, expirados)
  - Filtros por status
  - Grid de cards com acoes: copiar Pix, confirmar, cancelar
  - Modal "Nova cobranca Pix" (valor, descricao, paciente, chave opcional)
  - Modal de detalhe com BR Code copia-e-cola

---

## Sprint 8 — Hardening e qualidade (entregas 2026-04-17)

### Cobertura de testes ampliada: 64 -> 90 (+26)

**Novos testes:**
- `tests/test_pix_payload.py` (5 testes)
  - Formato TLV, CRC16-CCITT, estrutura do BR Code, validade do CRC, truncamento
- `tests/test_tenant_secrets.py` (4 testes)
  - Fallback para env quando nao ha integrations, preferencia por valores do tenant, provider default gemini, merge tenant+env
- `tests/test_tenancy_subdomain.py` (8 testes)
  - Host com porta, localhost, IP, apex domain, prefixos comuns (www/api/admin/app), case-insensitive
- `tests/test_payment_service.py` (9 testes)
  - Validacoes (amount>0, chave Pix obrigatoria), emissao, confirmacao (happy path + rejeicao de cancelled + idempotencia), webhook reconcilia pending->paid, erro para external_id ausente, sanitizacao ASCII

### Auditoria e correcoes de hardening

**CSRF — aplicado em 6 mutations que estavam desprotegidas:**
- `POST /api/v1/admin/tenants` (create_tenant)
- `PUT /api/v1/admin/tenants/<id>` (update_tenant)
- `PUT /api/v1/admin/tenants/<id>/branding`
- `PUT /api/v1/admin/tenants/<id>/integrations` (CRITICO — permitia injecao de credenciais)
- `PUT /api/v1/admin/tenants/<id>/plan`
- `POST /api/v1/admin/tenants/<id>/users`

Helper `_require_csrf()` adicionado em `src/web/routes/tenant_admin.py` espelhando o padrao do `api_v1._require_json_csrf()`.

**HMAC no webhook de pagamentos:**
- `_verify_payment_webhook_signature()` em `src/web/routes/payments.py`
- Valida X-Signature / X-Hub-Signature-256 / X-Webhook-Signature com HMAC-SHA256
- Secret por provedor: `PAYMENT_WEBHOOK_SECRET_<PROVIDER_UPPER>` (env)
- Em `FLASK_ENV=production`, eventos sem assinatura valida sao **rejeitados com 401**
- Fora de producao aceita mas loga `signature_ok=False` para auditoria
- `payment_webhook_log` agora reflete corretamente o valor de `signature_ok`

**Nao bloqueadores (mapeados mas nao corrigidos nesta sprint):**
- Twilio e Z-API webhooks em `realtime_notifications.py` ainda tem TODO stubs de assinatura (Sprint 3 legado; fora do escopo Sprint 8)
- Meta WhatsApp webhook (`_verify_hmac_meta`) ja valida corretamente

### Leitura de segredos
- `GET /api/v1/admin/tenants/<id>/integrations` chama `get_integrations(decrypted=False)` → valores retornados como `"***"` quando presentes, `null` quando ausentes. Nenhum secret trafega em cleartext na API de leitura.

---

## Validacao

- `pytest -q` -> **90 passed** (era 64; +26)
- `tsc --noEmit` -> ok

---

## Status final da plataforma

| Frente | Antes | Agora |
|--------|-------|-------|
| Multi-tenancy | Fundacao | **Operavel** — branding, subdominio, integrations por tenant, fallback gracioso para env |
| Billing e pagamentos | Fundacao | **Operavel** — emissao Pix, conciliacao via webhook HMAC, totais por status, log auditavel |
| Hardening e qualidade | Parcial | **Producao-ready** — CSRF em mutations, HMAC em webhooks externos, 90 testes verdes |

Todas as 8 sprints planejadas no progresso15 foram entregues.

---

## Proximos passos (sugestoes)

1. **Sprint 9 (opcional no plano original)** — PWA / app do paciente
2. **Integracao real de pagamentos** — conectar Mercado Pago, Gerencianet ou PagBank; a camada `process_webhook_event` ja e pronta para receber
3. **Cobertura E2E** — Playwright cobrindo fluxo triagem → atendimento → prescricao → pagamento
4. **Migrar secrets remanescentes** — `clinic_config` legado ainda le alguns valores direto de env; proximo ciclo pode centralizar tudo em tenant_integrations
5. **Observabilidade** — dashboards de Grafana com tenant_id nos logs (`extra={"tenant_id": ...}` ja e populado em `src/app.py`)

---

## Historico de sessoes

| Data | Sessao | Entregas |
|------|--------|----------|
| 2026-04-16 | Abertura | Auditoria completa, matriz de maturidade, plano de 9 sprints |
| 2026-04-16 | Sprint 1 | Migration 018 + triage_link persistido |
| 2026-04-16 | Sprint 2 | Limpeza de mocks em 6 telas medicas |
| 2026-04-16 | Sprint 3 | Modelo de conversas + inbox clinica |
| 2026-04-16 | Sprint 4 | Regulatory + monitors UI + retry/fallback Gemini |
| 2026-04-17 | Sprint 5 | Limpeza de mocks em 8 telas admin/org |
| 2026-04-17 | Sprint 6 | Multi-tenancy: migration 020, branding, integrations, secrets, subdomain, frontend detalhe |
| 2026-04-17 | Sprint 7 | Financeiro: migration 021, Pix EMV, emissao/conciliacao, frontend pagamentos |
| 2026-04-17 | Sprint 8 | Hardening: +26 testes, CSRF em 6 mutations, HMAC em webhook de pagamento |
