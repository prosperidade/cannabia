# Progresso 21 — SCC F4 + F5 fechamento (exceto F4.5)

**Data:** 2026-04-21
**Escopo da sessão:** sequenciar todas as fases pendentes do Sandbox Compliance Core até onde depende só de desenvolvimento, deixando F4.5 (5 planos obrigatórios, volume grande) e F4.1/F4.2 (Evidence Engine, depende de F2.5 inexistente) como únicas pendências puras.

---

## 1. Resumo executivo

**12 commits** entre `bb79718` e `a69a0e0` fecharam:

- **F4.3** templates registry + estrutura de subdirs
- **F4.4** template_engine genérico (resolve + render com content_hash SHA-256 + StrictUndefined)
- **F4.6 parte 1** Dossie migrado para o engine + 4 templates novos (parecer final, consentimento, rótulo, POP)
- **F4.6 resto** final/regulatory_report consolidado (com linked_documents por content_hash)
- **F4.7** review workflows — fluxo bilateral `draft→rt_review→legal_review→approved|rejected` + assinatura eletrônica mínima
- **F5.2** anchoring_service com Merkle bitcoin-convention + coleta multi-tabela + mock OTS
- **F5.3** integration opentimestamps (wrapper com pacote PyPI opcional + dispatcher provider)
- **F5.4** SandboxAnchor.sol + wrapper Python Polygon + dispatcher aceita 3 providers (mock/ots/polygon)
- **F5.5** endpoint público GET /api/v1/public/anchors/<tenant>/verify
- **F5.6** integration tests contra Postgres real
- **F5.7** upgrade job (pending→confirmed/failed) + runbook operacional

Também:
- **chore** frontend/tsconfig.json sem `baseUrl` deprecado

Suite final: **1132 passed, 0 failed**. Delta vs início da sessão (929): **+203 testes**.

---

## 2. Commits da sessão

| Hash | Descrição |
|------|-----------|
| bb79718 | templates(registry): manifest central + estrutura de subdirs — F4.3 |
| b39a264 | svc(templates): template_engine genérico — F4.4 |
| 24d2b9b | svc(anchoring): Merkle + mock OTS + pipeline — F5.2 |
| 5fd90a4 | routes(public): endpoint de verificação — F5.5 |
| b696a92 | tests(anchoring): integration e2e — F5.6 |
| 1ee4d9e | chore(frontend): remove baseUrl deprecado |
| cbfec96 | templates+svc: Dossie via engine + Parecer Final + complementares — F4.6 pt1 |
| e8759a8 | review-workflows: aprovação bilateral de regulatory_reports — F4.7 |
| eefe9ef | integrations(ots): OpenTimestamps wrapper + dispatcher — F5.3 |
| fe4ce48 | polygon: SandboxAnchor.sol + wrapper + dispatcher — F5.4 |
| 47b465a | anchor-upgrade: job + runbook — F5.7 |
| a69a0e0 | templates: Relatório Técnico-Regulatório Consolidado — F4.6 resto |

Todos pushados em origin/main.

---

## 3. Decisões arquiteturais desta sessão

### 3.1 Dispatcher de provider de ancoragem

`anchoring_service.submit_anchor(merkle_root, network, *, provider=None, ...)` seleciona o backend com prioridade:

1. Argumento explícito `provider=`
2. Variável de ambiente `ANCHORING_PROVIDER`
3. Default `'mock'`

Válidos: `mock` / `ots` / `polygon`. Cada provider valida a `network` esperada (OTS exige `bitcoin_ots`; Polygon exige `polygon`; mock aceita qualquer).

**Decisão de rede de produção (2026-04-21):** Polygon como backbone. Bitcoin OTS permanece selecionável para casos que exigem prova Bitcoin-grade (ex.: parecer final de experimento).

### 3.2 Pacotes PyPI opcionais

`web3` (Polygon) e `opentimestamps-client` (OTS) são **opcionais**. Os wrappers fazem import lazy e expõem um Protocol client injetável — testes rodam sem os pacotes, CI continua verde. Em produção, instalar e configurar as envs desbloqueia a submissão real.

### 3.3 Templates com StrictUndefined + [pendência] explícita

Providers (`build_*_data`) preenchem todas as chaves que o template referencia, mesmo que com `None`/`[]`/`''`. O template usa `{% if %}` + fallback textual `[pendencia: …]` para sinalizar gap de dados explicitamente (doc 27 §11.2 — evitar "dado incompleto mascarado"). Combinado com StrictUndefined, esse padrão impede geração silenciosa de documento incompleto.

### 3.4 Assinatura eletrônica mínima em review workflows

`signature_hash = SHA-256(report_id + from_status + to_status + action + actor_user_id + content_hash + reviewed_at_iso)` permite verificação independente pela recomputação dos campos. Não substitui ICP-Brasil mas satisfaz o requisito do progresso20 F4.7 ("hash + user_id + ts") e detecta adulteração de qualquer campo do step.

### 3.5 Contrato Solidity append-only

`SandboxAnchor.sol` não tem owner, selfdestruct ou admin. Qualquer wallet pode submeter (controle de acesso é off-chain no CannabIA). Imutabilidade é propriedade estrutural — sem caminhos de UPDATE/DELETE.

---

## 4. Arquitetura consolidada do domínio de ancoragem

```
 create_anchor(tenant_id, scope, covered_from, covered_until,
               blockchain_network, provider?)
   ├─ collect_anchorable_events → 4 tabelas (traceability/sop/regulatory/lab)
   ├─ build_merkle_root + build_merkle_proof (core puro, bitcoin-convention)
   ├─ submit_anchor(root, network, provider, ...)
   │    ├─ 'mock'    → submit_anchor_mock
   │    ├─ 'ots'     → src.integrations.opentimestamps.submit_to_ots
   │    └─ 'polygon' → src.integrations.polygon_anchor.submit_to_polygon
   │                     └─ contract SandboxAnchor.anchor(scope, scopeId,
   │                                                      merkleRoot, ...)
   └─ INSERT blockchain_anchors + N mappings (1 transação)
                                           │
                                           ▼ verification_status='pending'
                                           │
 anchor_upgrade_service.run_upgrade_sweep() — cron 5 min
   ├─ list_pending_anchors (idade ≥ 5 min)
   └─ upgrade_anchor(id) → probe(network) → UPDATE confirmed|failed
                                           │
 GET /api/v1/public/anchors/<tenant>/verify — F5.5
   └─ get_mappings_for_event → server_verified + merkle_path + tx
```

---

## 5. Estado do SCC

### 5.1 Fases fechadas

| Fase | Status | Notas |
|------|--------|-------|
| Fase 0 | ✅ 2026-04-19 | |
| F1.1 - F1.8 | ✅ 2026-04-20 | |
| F2.1 - F2.3 | ✅ 2026-04-20 | |
| F3.1 - F3.2 | ✅ 2026-04-20 | |
| **F4.3** | ✅ 2026-04-21 | registry + 1 template ativo |
| **F4.4** | ✅ 2026-04-21 | template_engine |
| **F4.6** | ✅ 2026-04-21 | 6 templates ativos (dossier + 5 novos) |
| **F4.7** | ✅ 2026-04-21 | migration 034 + review workflows |
| **F5.1** | ✅ 2026-04-20 | migration 033 |
| **F5.2** | ✅ 2026-04-21 | anchoring core |
| **F5.3** | ✅ 2026-04-21 | OTS wrapper |
| **F5.4** | ✅ 2026-04-21 | Polygon (código) |
| **F5.5** | ✅ 2026-04-21 | endpoint público |
| **F5.6** | ✅ 2026-04-21 | integration tests |
| **F5.7** | ✅ 2026-04-21 | upgrade job + runbook |

### 5.2 Pendências SCC (apenas 3 fases)

- [ ] **F4.5** — 5 planos obrigatórios (work_plan, communication_plan, discontinuity_plan, monitoring_plan, risk_management_plan) em Jinja2. Doc 27 §4. **Volume grande** — sessão dedicada.
- [ ] **F4.1 / F4.2** — Evidence service + estudos observacionais. **Bloqueado por F2.5** (captura de desfechos pós-consulta na telemetria). F2.5 ainda não existe no backlog.

Tudo mais do SCC está fechado do ponto de vista de desenvolvimento.

---

## 6. Pendências operacionais (ops/deploy — fora de desenvolvimento puro)

Registradas no [RUNBOOK_ANCHORING.md §8](RUNBOOK_ANCHORING.md#8-pendências-registradas) e replicadas aqui para visibilidade:

- [ ] **Deploy do contrato SandboxAnchor em Polygon Amoy** (hardhat/foundry; ver [contracts/README.md](../contracts/README.md))
- [ ] **Verificação do bytecode** no Polygonscan (requisito regulatório)
- [ ] **Exportar `POLYGON_SANDBOX_ANCHOR_ADDRESS`** no ambiente de produção
- [ ] **Instalar** `web3` e `opentimestamps-client` no prod env
- [ ] **Plugar** `_ProductionPolygonClient.anchor()` com web3.py (sign + send tx + decode event)
- [ ] **Plugar** `_ProductionOtsClient.stamp()` com `opentimestamps-client` (DetachedTimestampFile + RemoteCalendar)
- [ ] **Criar** `scripts/anchor_upgrade_cron.py` + agendar cron 5 min
- [ ] **Multi-sig** na wallet de deploy quando promover para mainnet
- [ ] **Alertas + métricas** conforme RUNBOOK §6 (Grafana ou equivalente)

---

## 7. Pendências para a próxima sessão (amanhã)

Ordem sugerida de ataque:

### Prioridade 1 — F4.5 (sessão dedicada)

5 planos obrigatórios do Projeto Experimental, cada um com estrutura declarada em doc 27 §4:

1. **work_plan** (§4.1) — 12 seções; dados de tenants, associations, technical_responsibles, technical_operational_capacity, sops ativos, sandbox_projects
2. **communication_plan** (§4.2) — 9 seções; com regra invariante de bloqueio de publicidade
3. **discontinuity_plan** (§4.3) — 10 seções; inventário atual + associados em tratamento
4. **monitoring_plan** (§4.4) — 9 seções; 10+ indicadores parametrizáveis pelo edital
5. **risk_management_plan** (§4.5) — 9 seções; matriz de riscos + CAPAs

Para cada: template `project_plans/<name>_v1.md.j2`, provider em `regulatory_documents.py`, testes. Mover do `planned_templates` para `templates` no registry.

**Esforço estimado:** dia inteiro. Os templates são longos (ANVISA-ready) e a consulta jurídica valida texto final em revisão futura (doc 27 §11.5). MVP aceitável: esqueleto + placeholders `[pendencia]` + provider agregando dados existentes, com nota de que texto substantivo é responsabilidade do RT.

### Prioridade 2 — F2.5 (destravar F4.1/4.2)

Desenhar e escrever migration + service de captura de desfechos pós-consulta. Necessário para o Evidence Engine. **Não está no BACKLOG_SCC original**, é uma dependência implícita descoberta. Avaliar escopo com stakeholders antes de começar.

### Prioridade 3 — operações

Se a Prioridade 1 e 2 forem grandes demais, atacar tickets operacionais (deploy Polygon Amoy, plugar clients reais). Isso destrava testes end-to-end completos com rede real.

---

## 8. Infraestrutura local e variáveis de ambiente

### 8.1 Envs novas introduzidas nesta sessão

```env
# Seleção de provider de ancoragem (default 'mock')
ANCHORING_PROVIDER=mock        # ou 'ots' | 'polygon'

# Polygon (F5.4) — necessárias quando ANCHORING_PROVIDER=polygon
POLYGON_NETWORK=amoy           # ou 'mainnet'
POLYGON_RPC_URL=https://rpc-amoy.polygon.technology
POLYGON_DEPLOYER_PRIVATE_KEY=0x...
POLYGON_SANDBOX_ANCHOR_ADDRESS=0x...
```

OTS não exige envs adicionais além da instalação do pacote `opentimestamps-client`.

### 8.2 Comandos-chave

```bash
# Start local stack
docker start cannabia-postgis
python -m src.app &
cd frontend && npm run dev

# Rodar suite completa
pytest -q

# Verificar que nada do SCC quebrou apos refactor
pytest tests/test_anchoring_service.py tests/test_anchoring.py \
       tests/test_opentimestamps.py tests/test_polygon_anchor.py \
       tests/test_anchor_upgrade_service.py \
       tests/test_template_engine.py tests/test_regulatory_documents.py \
       tests/test_document_review_service.py tests/test_document_review_routes.py \
       tests/test_migration_034_review_workflows.py \
       tests/test_public_anchors_routes.py -q
```

### 8.3 Usuários de dev (inalterados da sessão anterior)

admin/admin123 (Admin) · medico/medico123 · atendente/atendente123 · paciente/paciente123 · triage token `DEV-TRIAGE-2026`.

---

## 9. Notas operacionais importantes

### 9.1 Append-only em traceability_events e cleanup de testes

`traceability_events` tem trigger `prevent_update_delete` (migration 030) que bloqueia DELETE em produção. Fixtures de integration tests que precisam limpar rows dessa tabela devem usar:

```python
cursor.execute("SET LOCAL session_replication_role = 'replica'")
```

Isso pula triggers apenas na sessão transacional do teardown. Requer superuser/REPLICATION — o usuário de dev local tem.

### 9.2 Role names no document_reviews

`get_effective_roles()` retorna roles **normalizadas** (`"Admin"`, `"Medico"`, etc) via `ROLE_ALIASES`. Dicts de autorização devem usar essa forma (não lowercase). Bug sutil detectado e corrigido em `_ROLE_BY_ACTION` de `document_reviews.py`.

### 9.3 JSONB auto-decodificado pelo psycopg2

Colunas JSONB (`merkle_path`, `cannabinoid_profile`, etc.) vêm como list/dict Python direto — não precisa `json.loads`. Validado em `get_mappings_for_event` e `test_anchoring.py::test_merkle_path_do_db_reconstroi_raiz`.

### 9.4 Schema migrations.filename

Ao registrar migrations manualmente (como fiz para 034), incluir a coluna `filename`:

```python
cursor.execute(
    "INSERT INTO schema_migrations (version, filename, checksum) "
    "VALUES (%s, %s, %s) ON CONFLICT (version) DO UPDATE SET checksum = EXCLUDED.checksum",
    (version, filename, checksum),
)
```

Sem `filename`, viola NOT NULL.

---

## 10. Próxima sessão — start aqui

1. Ler este doc + MEMORY.md atualizado (`project_sprint_progress.md`).
2. Subir stack: `docker start cannabia-postgis`, `python -m src.app`, `cd frontend && npm run dev`.
3. Decidir prioridade 1 (F4.5) vs 2 (F2.5 + F4.1/4.2) com base em urgência regulatória.
4. Se F4.5: atacar um plano por vez; template + provider + testes + registry em sequência. Aproveitar fixtures de test_regulatory_documents.py como base. Renderização pura com contexto hand-crafted é o caminho mais rápido para validar estrutura; aggregators complexos ficam para iteração.
5. Se F2.5: desenhar migration com stakeholders primeiro. É trabalho de discovery de produto, não só de código.

**Suite:** 1132 passed, 0 failed. Origin/main sincronizado em `a69a0e0`.
