# Progresso 24 — App unificado da clínica + roles refinadas + Fase A2 (sidebar dinâmico)

**Data:** 2026-04-26
**Escopo:** primeiro dia pós-SCC. Foco em destravar o uso do produto pelo time da clínica. Sequência: popular DB → refinar roles → conserto de bugs urgentes → reescrever UI de configurações → estender backend → sidebar dinâmico por role.

---

## 1. Resumo executivo

7 commits hoje entre `01d2bb0` e `037104b`:

| Hash | Descrição curta |
|------|-----------------|
| `01d2bb0` | seed: `seed_scc.py` complementar + fix user_id em `seed_comprehensive` |
| `909ac9c` | auth: roles refinement com `is_clinic_admin` + Recepcao/Financeiro/AdminClinica |
| `e8a114e` | fix: logout robusto + placeholder `/admin/sistema` |
| `1130550` | ui: nova `/org/configuracoes` com abas + sidebar refinado |
| `1cfdcae` | ui: remove "Configurações" duplicado no rodapé do sidebar |
| `28fb25a` | config: persistência completa via `tenant_settings` JSONB |
| `037104b` | ui: sidebar dinâmico por role + `is_clinic_admin` + `tenant_type` (Fase A2) |

Tudo pushed em `origin/main`. **Suite: 1458 passed, 0 failed.**

---

## 2. Decisões arquiteturais novas

### 2.1 Roles refinadas (substitui `Atendente` e cria flag combinável)

| Role | Escopo |
|---|---|
| `Admin` (global) | Super admin da plataforma — só `/admin` |
| `Medico` | Atendimento clínico |
| `Recepcao` | Operação do dia (era `Atendente`, renomeado) |
| `Financeiro` | Estoque, faturamento, financeiro, campanhas |
| `AdminClinica` | Gestão da clínica/associação sem perfil clínico |
| `Paciente` | Portal paciente |

**Flag `users.is_clinic_admin BOOLEAN`** combinável com qualquer role. Resolve "médico-dono" sem múltiplos roles:

- `Medico + is_clinic_admin=TRUE` → médico-dono (vê Modo Médico **e** todas as seções administrativas)
- `Medico + is_clinic_admin=FALSE` → médico assalariado (só Modo Médico)
- `AdminClinica + is_clinic_admin=TRUE` → admin local não-médico

### 2.2 ROLE_ALIASES corrigido

`clinic_admin / tenant_admin / org_admin / organization_admin` no `user_clinics.role` agora mapeiam para **`AdminClinica`** (era `Admin`). Antes, qualquer admin de tenant local virava super admin global — confusão semântica. Agora:

- `Admin` = super admin da plataforma
- `AdminClinica` = admin de UM tenant específico

`get_effective_roles()` foi atualizado para incluir `AdminClinica` automaticamente quando `current_user.is_clinic_admin=True`.

### 2.3 `tenant_settings` JSONB como backing store das configurações

Em vez de criar 4-5 tabelas dedicadas (operacional, integracoes, dna, notificações), usamos UMA tabela JSONB única por tenant:

```sql
CREATE TABLE tenant_settings (
  tenant_id INT PRIMARY KEY REFERENCES tenants(id),
  settings JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_by INT REFERENCES users(id)
);
```

Estrutura do JSONB:
```json
{
  "cadastro":      { "cnpj", "address", "phone", "email" },
  "operacional":   { "weekdayOpen", "consultationPrice", ... },
  "integracoes":   { "whatsappNumber", "apiKeyMeta", "apiKeyOpenAI",
                     "apiKeyGemini", "smtpHost", "smtpUser", "smtpPassword" },
  "businessDna":   { "businessMission", "targetPatientProfile",
                     "agentToneOfVoice", "internalPolicies" },
  "notificacoes":  { "notifyEmailNewPatient", ... }
}
```

Razão: schema flexível, vai iterar muito na Fase A2; não precisa migration cada vez que UI ganha um campo.

**Limitação registrada:** chaves sensíveis (apiKey*, smtpPassword) ficam em texto plano em DEV. Em PROD, encriptar via `tenant_secrets` (sprint futura).

### 2.4 Catálogo central de navegação (`frontend/lib/nav.ts`)

3 catálogos (`ADMIN_NAV`, `ORG_NAV`, `MED_NAV`), cada item com `visibleFor`:

```ts
{
  label: "Estoque",
  href: "/org/estoque",
  visibleFor: {
    roles: ["Admin", "AdminClinica", "Financeiro"],
    orClinicAdmin: true,
    tenantTypes: ["association"],
  },
}
```

`filterNav(catalog, ctx)` aplica role + is_clinic_admin + tenant_type em uma só passada. Cada layout (`/admin`, `/med`, `/org`) chama com seu catálogo.

`getRoleRedirect(role, isClinicAdmin)` decide pós-login. **Médico-dono** vai pra `/org/dashboard`; médico puro pra `/med/dashboard`.

### 2.5 Distinção `/admin` vs `/org` clarificada

- `/admin` = super admin da **plataforma** (multi-tenant, raríssimo)
- `/org` = app da **clínica/associação** (médico, recepção, financeiro, admin local)
- `/med` = subset de "modo médico" para médico assalariado puro (consolidação em `/org` fica para Fase A2 final)

### 2.6 Logout robusto

Os 3 layouts agora usam `window.location.href = "/login"` no `finally` em vez de `router.push`. Razão: Next 15 + cookie clearing pode deixar state cacheado do React/RSC vivo, o que causava loop visual de "voltar pra dashboard após Sair". `window.location` força reload completo.

---

## 3. UI novas / refeitas

### 3.1 `/org/configuracoes` — substitui `/org/config`

Layout em **abas** (sidebar vertical em desktop, horizontal scroll em mobile) com header sticky e botão Salvar global. 6 abas:

1. **Identidade Visual** — logo URL, brand name, subdomain (white-label), cor primária + destaque (presets + color picker), preview live
2. **Clínica/Associação** — razão social, CNPJ, endereço, contato
3. **Operacional** — horários (semana/sábado/domingo), valor consulta, duração, modalidades
4. **Integrações** — WhatsApp + Meta token, OpenAI + Gemini API keys, SMTP host/user/password, Pix
5. **DNA do Negócio** (NOVO) — missão, ICP, tom de voz dos agentes, políticas internas. **Personaliza comportamento dos agentes IA do tenant.**
6. **Notificações** — toggles por evento (email + WhatsApp)

`/org/config` agora redireciona para `/org/configuracoes`.

### 3.2 `/org/acompanhamento` — skeleton

Página dedicada ao cuidado contínuo dos pacientes entre consultas (output dos agentes IA: Triagem, FollowUp, Regulatorio).

4 KPIs no topo (pacientes em risco, follow-ups pendentes, triagens em andamento, eventos adversos abertos) + cards "alertas para a equipe", "atividade dos agentes nas últimas 24h", "pacientes em acompanhamento ativo". Tudo em estado vazio — endpoints reais entram na próxima sprint.

Visível para: `Medico`, `Recepcao`, `AdminClinica`, `Admin`.

### 3.3 `/org/conhecimento` e `/med/conhecimento` — placeholders

Item "Base Científica" no sidebar de médico/admin_clinica. UI real (busca PubMed/legislação escopada por tenant) entra na próxima sprint.

### 3.4 Sidebars unificados via filtro

| Login | Vai para | Sidebar |
|---|---|---|
| `admin` | `/admin` | 7 itens super admin |
| `dono` | `/org/dashboard` | tudo de clínica + Modo Médico + Configurações |
| `medico` puro | `/med/dashboard` | só Modo Médico + Acompanhamento + Mensagens + Base Científica + Conformidade |
| `recepcao` | `/org/acompanhamento` | Painel + Agendamentos + Mensagens + Pacientes + Acompanhamento |
| `financeiro` | `/org/financeiro` | Painel + Faturamento + Financeiro + Campanhas + (Estoque se tenant=association) |
| `admin_clinica` | `/org/dashboard` | Operação + Conformidade + Configurações + Médicos |
| `paciente` | `/p/dashboard` | mobile separado |

---

## 4. Backend

### 4.1 Migration 038 — `is_clinic_admin` + Recepcao

```sql
ALTER TABLE users ADD COLUMN is_clinic_admin BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE users SET role='Recepcao' WHERE role='Atendente';
UPDATE user_clinics SET role='recepcao' WHERE role='atendente';
```

### 4.2 Migration 039 — `tenant_settings`

Tabela JSONB com seção 2.3 acima.

### 4.3 `clinic_config.py` reescrito

GET retorna shape achatado lendo de 3 fontes (`clinics.name` + `tenant_branding` + `tenant_settings`). PATCH aceita o mesmo shape e distribui. Permissões:

- GET: Admin / AdminClinica / Medico / Recepcao / Financeiro
- PATCH: só `Admin` global ou `is_clinic_admin=TRUE`

### 4.4 `seed_users.py` atualizado

7 users dev representativos:

| Usuário | Senha | Role | is_clinic_admin |
|---|---|---|---|
| `admin` | `admin123` | Admin | False |
| `dono` | `dono123` | Medico | **True** |
| `medico` | `medico123` | Medico | False |
| `recepcao` | `recepcao123` | Recepcao | False |
| `financeiro` | `financeiro123` | Financeiro | False |
| `admin_clinica` | `adminclinica123` | AdminClinica | True |
| `paciente` | `paciente123` | Paciente | False |

### 4.5 `seed_scc.py` complementar (commit 01d2bb0)

Popula governance + members + sandbox + adverse_events que `seed_comprehensive.py` não cobria. Idempotente. **Estado final do tenant 1:**

```
patients                        15
association_members              5
institutional_documents          3
technical_responsibles           2
sanitary_risks                  10
sops                            10
sandbox_projects                 1 (PROJ-SEED-001 active)
sandbox_indicators               3 (1 on_target, 2 off_target)
sandbox_indicator_values         9
adverse_events                   6 (3 mild, 1 moderate, 2 severe)
pharmacovigilance_notifications  2
```

---

## 5. Bugs capturados e corrigidos

| # | Sintoma | Causa | Fix |
|---|---|---|---|
| 1 | `seed_comprehensive.py` quebrava com FK violation `user_id=8` | hardcoded user_id baseado em sequence antiga | resolve `user_id` via SELECT do user `paciente` em runtime |
| 2 | "Login do paciente travado" | bug de envelope `/patient/profile` (front esperava `data.patient`, API retorna campos top-level) | declarado como bug conhecido, fix fica para sprint do app paciente |
| 3 | Cards do dashboard paciente apontavam para 404 (`/p/documentos`, `/p/consultas`) | rotas nunca foram criadas | declarado como bug conhecido (paciente baixa prioridade) |
| 4 | `/admin/sistema` dava 404 | item no sidebar mas pasta nunca criada | criado placeholder; depois removido o item do sidebar de vez |
| 5 | Logout não saía (loop voltando pra dashboard) | `router.push` não descarta state cacheado quando cookie zerado | `window.location.href = "/login"` no finally |
| 6 | UI inteira "desconfigurada" (ícones aparecendo como texto) | dev server do Next 15 travado em hot reload | reiniciar `npm run dev` (não era código) |
| 7 | Sidebar com "Configurações" duplicado | link fixo em `sidebar-layout.tsx` (rodapé) + item dinâmico em cada layout | removido o link fixo |
| 8 | Teste `test_compliance_overview` quebrou após seed_scc | `seed_scc.py` reservava CRM 12345/SP que colidia com fixture do teste | fixture passa a usar council_number gerado por uuid |

---

## 6. Pendências para a próxima sessão (em ordem)

### Prioridade 1 — Base Científica real escopada por tenant
- Refatorar `/admin/knowledge` para servir tanto super admin quanto admin local
- Endpoint `/api/v1/knowledge/search` filtrado por tenant
- UI `/org/conhecimento` ganha busca real (artigos PubMed + legislação ANVISA via Google Files API)

### Prioridade 2 — `/org/acompanhamento` com dados reais
- Plugar 4 KPIs em endpoints reais:
  - "Pacientes em risco" → filtros sobre `adverse_events` (severe+life_threatening sem `clinical_assessment`)
  - "Follow-ups pendentes" → `scheduled_followups` com `responded_at IS NULL` na janela
  - "Triagens em andamento" → integração com agente de triagem (a definir)
  - "Eventos adversos abertos" → `adverse_events.outcome IS NULL`
- Atividade dos agentes (ai_audit_logs)
- Listagem de pacientes em acompanhamento ativo

### Prioridade 3 — Página inicial dinâmica por role
- `getRoleRedirect` já direciona corretamente, mas a tela de chegada é a mesma para todos
- Recepção quer ver agenda do dia + acompanhamento
- Médico quer ver fila + retornos pendentes
- Dono quer ver KPIs gerais

### Prioridade 4 — App paciente (`/p/*`)
- Bug de envelope no `/patient/profile`
- Criar pastas `/p/documentos` e `/p/consultas` (cards do dashboard apontam pra elas)
- Decisão: continuar como `/p/*` no Next ou virar app nativo separado?

### Prioridade 5 — Refatorar agentes IA (1 por vez)
- BaseAgent + 6 agentes (Triagem, Anamnese, Prescritor, Científico, Regulatório, FollowUp)
- Memória interna própria (Postgres/ChromaDB — **não** MemPalace)
- Conectar com DNA do Negócio (`tenant_settings.businessDna`)
- Já temos: skill `triage_adverse_event` no `regulatorio.py` (F3.4)

---

## 7. Como retomar amanhã

```bash
# 1. Status do projeto
git -C c:/Users/Administrador/Desktop/Cannabia log --oneline -10

# 2. Subir stack
docker start cannabia-postgis              # postgres :5434
env/Scripts/python.exe -m src.app          # backend :5000
cd frontend && npm run dev                 # frontend :3001

# 3. Suite — confirmar baseline
env/Scripts/python.exe -m pytest -q
# Esperado: 1458 passed

# 4. Logar como dono/dono123 e validar:
#    - Sidebar tem todas as seções administrativas
#    - /org/configuracoes salva todos os campos
#    - /org/acompanhamento abre (cards vazios)
```

**Próximo item da agenda:** Base Científica real escopada por tenant (Prioridade 1).

---

**Suite:** 1458 passed, 0 failed.
**Origin/main:** sincronizado em `037104b`.
**Foco:** próxima sessão é destravar "Base Científica" + "Acompanhamento" com dados reais.
