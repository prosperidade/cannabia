# Progresso 20 — Governance Hub (F1) completo + crypto schema (F5.1)

**Data:** 2026-04-20
**Escopo da sessao:** fechar Fase 1 inteira do BACKLOG_SCC.md (F1.3 → F1.8) com
extensao multi-tenant para Admin, e abrir Fase 5 com a migration 033
(blockchain_anchors + anchor_event_mappings).

---

## 1. Resumo executivo

Em uma sessao, fechamos:

- **F3.2** migration 032_regulatory_schema (6 tabelas sandbox + regulatory)
- **F1.3** governance_repository (17 funcoes CRUD sobre as 4 tabelas de 025)
- **F1.4** governance_service com validacao de elegibilidade (EligibilityReport + 5 findings)
- **F1.5 parte 1** blueprint `/api/v1/governance` (13 endpoints CRUD + eligibility)
- **F1.5 parte 2** Dossie de Elegibilidade (template Jinja2 + renderer + endpoint)
- **F1.5 extensao** Admin multi-tenant overview (novo endpoint + UI)
- **F1.6** skill `check_sandbox_eligibility` no AgenteRegulatorio
- **F1.7** frontend Governance Hub (`/org/sandbox/governance` + `/admin/sandbox`)
- **F1.8** integration tests e2e (19 testes contra Postgres real)
- **F5.1** migration 033_crypto_schema (2 tabelas + 6 CHECKs + 4 indices)
- **Fix colateral** Suspense boundary em `/triagem` (pre-existente, bloqueava next build)

Suite final: **929 passed** (antes da sessao: 789). Delta: +140 testes.

---

## 2. Commits da sessao

| Hash | Descricao |
|------|-----------|
| 696cdc1 | migrations(032): regulatory schema — F3.2 |
| 3ac5315 | repo(governance): CRUD das 4 tabelas — F1.3 |
| 079f3bc | svc(governance): validacao de elegibilidade sandbox — F1.4 |
| 9a7de63 | routes(governance): CRUD + eligibility endpoints — F1.5 parte 1 |
| 606bde6 | routes(governance): Dossie de Elegibilidade — F1.5 parte 2 |
| 4a01f23 | agent(regulatorio): skill check_sandbox_eligibility — F1.6 |
| b3087b6 | frontend(governance): Governance Hub UI — F1.7 |
| c1abebf | fix(triagem): wrap useSearchParams em Suspense boundary |
| 7942d5a | routes+ui(governance): Admin multi-tenant sandbox overview |
| b6eaf30 | tests(governance): integration e2e — F1.8 |
| 01077e8 | migrations(033): crypto schema — F5.1 |

11 commits, branch `main`, origin/main desatualizado — precisa push.

---

## 3. Arquitetura consolidada do Governance Hub

### 3.1. Camadas

```
 Frontend (Next.js)
 ├── /org/sandbox/governance/page.tsx        — visao por tenant (Atendente)
 └── /admin/sandbox/page.tsx                 — visao multi-tenant (Admin)
        │
        ▼  (fetch via lib/governance.ts, tipado, credentials: include)
 Backend (Flask blueprint governance_bp)     — /api/v1/governance/**
        │
        ▼  (regras de elegibilidade + transicoes de status)
 Service governance_service.py
  ├── check_sandbox_eligibility() → EligibilityReport com 5 findings
  ├── refresh_eligibility()       → marca validated + transiciona 'preparing'
  └── list_all_associations_summary() → agrega multi-tenant (admin only)
        │
        ▼  (sem regras de negocio, so acesso a dados)
 Repository governance_repository.py         — 17 funcoes CRUD
        │
        ▼  (SQL puro)
 Postgres (migration 025)
  ├── associations (1:1 com tenants tipo association)
  ├── institutional_documents
  ├── technical_responsibles  (UNIQUE conselho/numero/UF)
  └── technical_operational_capacity (snapshots de readiness)
```

### 3.2. Geracao de documento regulatorio

```
 service governance_dossier.py
  ├── build_dossier_data(tenant_id) → dict pronto p/ template
  └── render_dossier_markdown()     → Markdown via Jinja2 (StrictUndefined)
        │
        ▼
 data/templates/eligibility/dossier_v1.md.j2  — 10 secoes (doc 27 §5)
```

### 3.3. Skill de IA

```
 AgenteRegulatorio.check_sandbox_eligibility(tenant_id | association)
  → wrapping do service, empacota com blockers[].action (apontando o
    endpoint REST correto), compativel com Orchestrator.
  → diary fire-and-forget no palace_room 'regulatorio_anvisa'.
```

---

## 4. Estado do SCC (docs/BACKLOG_SCC.md)

### 4.1. Fases fechadas

| Fase | Status | Notas |
|------|--------|-------|
| Fase 0 (Hardening) | Concluido 2026-04-19 | |
| F1.1 (migration 024) | Concluido | |
| F1.2 (migration 025) | Concluido | |
| **F1.3-F1.8 (codigo Python/TS)** | **Concluido 2026-04-20** | 11 commits desta sessao |
| F2.1 (migration 026) | Concluido | |
| F2.2 (migration 027) | Concluido | |
| F2.3 (migrations 028-030) | Concluido | |
| F3.1 (migration 031) | Concluido | |
| **F3.2 (migration 032)** | **Concluido 2026-04-20** | |
| **F5.1 (migration 033)** | **Concluido 2026-04-20** | |

### 4.2. Pendencias para amanha (ordem sugerida de ataque)

**Prioridade 1 — fundacao de documentos regulatorios:**

- [ ] **F4.3** — `data/templates/registry.yaml` + estrutura conforme doc 27 §2
      (subdirs `eligibility/`, `plans/`, `monitoring/`, `complementary/`).
      Catalogar o `dossier_v1.md.j2` existente no registry. Prep para F4.4.

- [ ] **F4.4** — `src/services/template_engine.py`. Generaliza o renderer que
      ja existe em `governance_dossier.py`. Interface sugerida:
      `render(template_id, context, format='md')`. Resolve template_id via
      registry, aplica versionamento, hash do output (para content_hash
      em regulatory_reports). Reutiliza a validacao StrictUndefined do
      governance_dossier.

**Prioridade 2 — imutabilidade e ancoragem (F5 continua):**

- [ ] **F5.2** — `src/services/anchoring_service.py`. Calculo Merkle diario
      (arvore binaria balanceada a partir de hashes de traceability_events
      + adverse_events + dispensations + lab_analyses + regulatory_submissions).
      Submissao via mock OpenTimestamps primeiro (integracao real fica F5.3).
      Escreve em blockchain_anchors com verification_status='pending' e em
      anchor_event_mappings com merkle_path.

- [ ] **F5.6** — `tests/test_anchoring.py`. Testar calculo de raiz contra
      vetor conhecido, geracao de proof, verificacao de proof valida e
      rejeicao de proof adulterada.

- [ ] **F5.5** — `GET /public/anchors/<tenant_id>/verify?event_id=...&table=...`.
      Endpoint publico (sem auth) que retorna merkle_path + raiz + transaction_id,
      permitindo verificacao independente por terceiros.

- [ ] **F5.3** — `src/integrations/opentimestamps.py`. Substitui o mock de
      F5.2 pela submissao real ao protocolo OTS (Bitcoin). Requer
      `opentimestamps-client` do PyPI.

**Prioridade 3 — completa F4 com o que ja tem base:**

- [ ] **F4.6** — Migra o Dossie atual (hoje em governance_dossier) para usar
      o template_engine generalizado de F4.4. Adiciona:
      - Parecer Final de Monitoramento (doc 27 §6)
      - Documentos complementares (termo de consentimento, rotulo, template
        POP — doc 27 §7)
      Cada template vai para seu subdir no registry.

- [ ] **F4.7** — Fluxo de aprovacao bilateral. Requer:
      - `document_review_workflows` tabela? avaliar se cabe em migration 034
        ou e coluna em `regulatory_reports`
      - Endpoints `POST /reports/<id>/review` com status (draft/rt_review/
        legal_review/approved/rejected)
      - Assinatura eletronica minimamente registrada (hash + user_id + ts)

**Prioridade 4 — dependencias externas (decisoes humanas):**

- [ ] **F5.4** — Deploy do smart contract Polygon. Precisa de wallet com gas
      budget. Decisao: mainnet vs amoy testnet inicial. Fora do escopo
      de dev puro.

- [ ] **F5.7** — Runbook operacional. Cadencia de ancoragem, retry em falha
      de rede, tratamento de reorg de Bitcoin, fallback para Polygon quando
      Bitcoin OTS esta com fila grande.

- [ ] **F4.5** — 5 planos obrigatorios do Projeto Experimental em Jinja2.
      Volume grande — cada plano e um documento ANVISA-ready extenso. Melhor
      atacar depois que F4.4 estiver bem testado e F4.3 consolidado.

**Prioridade 5 — evidence engine (depende de F2.5 que ainda nao existe):**

- [ ] **F4.1/F4.2** — Evidence service + estudos observacionais. Precisa da
      F2.5 (capture de desfechos na telemetria pos-consulta). Deixa por
      ultimo.

---

## 5. Infraestrutura local e seeds

### 5.1. Usuarios de desenvolvimento (scripts/seed_users.py)

| Username | Senha | Role | Observacao |
|----------|-------|------|------------|
| admin | admin123 | Admin | Promovido manualmente de Medico nesta sessao |
| medico | medico123 | Medico | |
| atendente | atendente123 | Atendente | |
| paciente | paciente123 | Paciente | |

Todos com vinculo em `user_clinics` na clinica padrao (id=1).

### 5.2. Triage link dev

Token fixo para testar trilha publica sem gerar novo:
```
http://localhost:3001/triagem?token=DEV-TRIAGE-2026
```
Valido ate 2026-05-20. Clinic_id=1.

### 5.3. Setup de execucao local

- **Postgres:** Docker `cannabia-postgis:5434` (postgis/postgis:16-3.5-alpine)
- **Backend:** `python -m src.app` (porta 5000, debug mode com SocketIO)
- **Frontend:** `npm run dev` em `frontend/` (porta **3001**, hot reload).
  NAO usar `npm run start` (porta 3000) em dev — ele serve build estatico
  e nao pega rotas novas sem rebuild.

### 5.4. Decisoes arquiteturais confirmadas

1. **Template de Dossie com StrictUndefined:** forca fixture de teste
   completa, pega typos do template em tempo de renderizacao.
2. **Fallback de action em agente regulatorio:** `_action_for()` traduz
   codes conhecidos em passos operacionais, mas codes desconhecidos caem
   para a message crua do finding — mantem forward-compat quando novos
   checks sao adicionados ao service.
3. **tenant_id NULLABLE em blockchain_anchors:** suporta anchor_scope='global'
   (ancoragens de plataforma que cobrem multiplos tenants). Validacao do
   par (scope, tenant_id) fica no service, nao em CHECK, para evitar
   acoplamento ruim.
4. **Sem triggers append-only em blockchain_anchors:** verification_status
   precisa transitar apos confirmacao on-chain. Imutabilidade vem das
   hashes (merkle_root, proof_hash), nao da tabela.

---

## 6. Notas operacionais

### 6.1. Conftest.py agora carrega .env

Adicionamos `_load_project_dotenv()` no conftest para que integration
tests (como `test_governance.py`) leiam `DATABASE_URL` do projeto antes
do snapshot em `src.config`. Nao sobrescreve `TEST_DATABASE_URL` ou
vars do shell.

### 6.2. Testes de integracao com skip automatico

`test_governance.py` faz `pytest.mark.skipif(not _db_reachable())` no
modulo inteiro. CI sem docker-compose nao quebra.

### 6.3. Build do frontend

Next 16 exige `<Suspense>` em torno de componentes que usam
`useSearchParams()`. `/triagem` estava quebrando builds. Corrigido em
c1abebf. Manter em mente ao adicionar novos pages client-side que lem
query params.

### 6.4. schema_migrations.checksum

`VARCHAR(64)` cabe SHA-256 hex exato. Ao registrar migrations manualmente
via shell, usar `tr -d '\r\n '` no output do hashlib para evitar
trailing whitespace que estoura o tamanho.

---

## 7. Proxima sessao — start aqui

1. Ler este doc + MEMORY.md atualizado.
2. Subir stack local: `docker start cannabia-postgis`, `python -m src.app` em
   um terminal, `cd frontend && npm run dev` em outro.
3. Comecar por **F4.3** (templates registry) — rapido e destrava F4.4.
4. Seguir para **F5.2** (anchoring_service) — peca mais valiosa de F5.
5. Evitar F4.5, F4.7, F5.4, F5.7 ate ter tempo dedicado — cada um e um dia
   inteiro sozinho.

Origin/main esta **11 commits atras** — push ja.
