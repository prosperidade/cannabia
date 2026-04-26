# Progresso 23 — F3 stack inteira fechada (SCC dev puro 100%)

**Data:** 2026-04-24 e 2026-04-25
**Escopo:** fechar a F3 (pharmacovigilance + regulatory reporting), última frente de dev puro do SCC. Após esta entrega, sobra apenas a F7 (piloto e parcerias — trabalho humano de produto/jurídico, fora do escopo de engenharia).

---

## 1. Resumo executivo

6 commits em 2 dias entre `26cdc4e` e `81671c4`:

| Hash | F | Descrição |
|------|---|-----------|
| `39232a4` | F3.3 | `adverse_event_service` + `adverse_event_repository` + 33 testes |
| `d83c3f0` | F3.4 | Skill `triage_adverse_event` heurística PT-BR no `regulatorio.py` + 13 testes |
| `26cdc4e` | F3.5 | `integrations/vigimed.py` wrapper de notificação regulatória + 32 testes |
| `24f1ddf` | F3.6 | `pharmacovigilance_service` + blueprint `pharmacovigilance.py` (8 rotas) + 45 testes |
| `0066e61` | F3.7 | `regulatory_reporting_repository` + blueprint (7 rotas read-only) + 48 testes |
| `81671c4` | F3.8 | E2E `tests/test_pharmacovigilance.py` (pipeline completo HTTP+DB sem mocks) + 8 testes |

**Suite final:** **1458 passed, 0 failed**. Delta da jornada F3: **+179 testes** (1279 → 1458).

Tudo pushed em `origin/main`.

---

## 2. O que ficou pronto

### 2.1 Endpoints HTTP novos disponíveis no backend

#### Painel médico/clínica de farmacovigilância (`/api/v1/pharmacovigilance`)
| Verbo | Rota | Função |
|-------|------|--------|
| POST | `/adverse-events` | Captura manual de evento adverso |
| GET | `/adverse-events` | Lista com filtros (severity, reported_via, member_id, has_triage, since/until) |
| GET | `/adverse-events/<id>` | Detalhe de um evento |
| PUT | `/adverse-events/<id>/clinical-assessment` | Parecer clínico do médico revisor |
| PUT | `/adverse-events/<id>/outcome` | Outcome (resolved/resolving/ongoing/worsened/unknown) |
| POST | `/adverse-events/<id>/triage` | Invoca a skill IA → grava `ai_triage_result` |
| POST | `/adverse-events/<id>/notify` | Submete notificação via dispatcher (mock/vigimed/notivisa) → grava |
| GET | `/adverse-events/<id>/notifications` | Histórico de notificações |
| GET | `/dashboard` | Snapshot epidemiológico (counts por severidade + por target) |

Auth: `@api_role_required("Admin", "Medico")` + CSRF nos writes.

#### Dashboards ANVISA-ready (`/api/v1/regulatory-reporting`)
| Verbo | Rota | Função |
|-------|------|--------|
| GET | `/projects` | Lista de sandbox_projects (filtro por status) |
| GET | `/projects/<id>` | Projeto + protocolo vigente (effective_until IS NULL) |
| GET | `/indicators` | View `v_sandbox_indicator_dashboard` com latest_value e on_target |
| GET | `/indicators/<id>` | Indicador + history para gráfico |
| GET | `/submissions` | regulatory_submissions (filtro `awaiting_response`) |
| GET | `/reports` | regulatory_reports (whitelist 7 tipos) |
| GET | `/overview` | KPIs top-level: counts + score de indicadores mandatórios on_target |

Auth: `@api_role_required("Admin", "Medico")`. Read-only (sem CSRF/writes).

> Distinção importante: `regulatory.py` (legislação via Google Files API) **continua como está**, prefixo `/api/v1/regulatory`. O novo é `regulatory_reporting.py`, prefixo `/api/v1/regulatory-reporting`.

### 2.2 Integração com WhatsApp

O webhook do WhatsApp **não passa pelo blueprint HTTP**. Quando o agente conversacional detectar relato de evento adverso, ele chama direto:

```python
from src.services.adverse_event_service import capture_adverse_event

capture_adverse_event(
    tenant_id=...,
    description="texto livre do paciente",
    severity="mild",  # default; triage IA pode escalar depois
    reported_via="whatsapp",
    member_id=None,   # paciente sem cadastro ainda
)
```

Depois o painel médico (HTTP) decide quando triar e notificar.

### 2.3 Triage IA determinística

Skill `triage_adverse_event` em `src/ai/agents/regulatorio.py` faz classificação **regex PT-BR** (não LLM) sobre 4 níveis: moderate / severe / life_threatening / fatal. Algoritmo max-rank: nunca baixa a severidade reportada pelo humano. Saída versionada em `TRIAGE_MODEL_VERSION="regulatorio-triage-v1-heuristic"` para auditabilidade quando trocarmos por modelo IA real no futuro.

### 2.4 Dispatcher de notificação regulatória

`src/integrations/vigimed.py` com 3 providers:
- **`mock`** (default em dev/CI): determinístico, sem rede, target = `internal_only`
- **`vigimed`**: stub — ativação exige creds ANVISA + lib oficial
- **`notivisa`**: stub — ativação exige integração estadual/municipal

Provider resolvido por: argumento explícito > env `ANVISA_NOTIFICATION_PROVIDER` > default `mock`.

---

## 3. Bugs capturados durante o desenvolvimento (todos corrigidos)

| F | Bug | Causa | Fix |
|---|-----|-------|-----|
| F3.6 | SELECT com JOIN gerava `column reference "id" is ambiguous` | Constante `_COLUMNS` sem alias de tabela | Criado `_COLUMNS_N` com prefixo `n.` para queries com JOIN |
| F3.7 | Testes esperavam `on_target=True` para 90 vs target 80 | View define `on_target = abs(latest-target)/abs(target) <= 0.05` (5% de tolerância, NÃO "atingiu o alvo") | Fixture ajustado para 82 vs 80 (2.5%) |
| F3.8 | E2E falhava com FK violation em `triaged_by → users.id` | Sessão Flask de teste usava id arbitrário (99) que não existia em `users` | Fixture E2E cria user Admin real no setup com cleanup |

---

## 4. Pendências operacionais (não-dev)

Coisas que **você ou ops** precisam fazer **fora do código** para destravar produção. Estado: nada disso bloqueia o frontend nem testes — tudo segue funcionando em mock.

### 4.1 Anchoring (F5.x — herdado de progresso21)

- [ ] Deploy do contrato `SandboxAnchor.sol` em Polygon Amoy (hardhat ou foundry)
- [ ] Verificação do bytecode no Polygonscan
- [ ] Exportar `POLYGON_SANDBOX_ANCHOR_ADDRESS` no `.env` de produção
- [ ] Instalar `web3` no env de produção: `pip install web3`
- [ ] Instalar `opentimestamps-client` em produção
- [ ] Plugar `_ProductionPolygonClient.anchor()` (sign + send tx + decode event) usando web3.py
- [ ] Plugar `_ProductionOtsClient.stamp()` usando opentimestamps-client
- [ ] Criar `scripts/anchor_upgrade_cron.py` e agendar cron 5min
- [ ] Multi-sig na wallet de deploy quando promover para mainnet
- [ ] Configurar alertas/métricas conforme RUNBOOK §6

### 4.2 Notificação regulatória (F3.5 — novo)

- [ ] Obter credenciais oficiais ANVISA / VigiMed (caminho ainda não documentado pela ANVISA — pode exigir convênio formal)
- [ ] Identificar lib/SDK oficial VigiMed (se existir; senão construir cliente HTTP a partir da especificação)
- [ ] Plugar `_ProductionVigiMedClient.submit()` em `src/integrations/vigimed.py`
- [ ] Mesmo processo para `_ProductionNotivisaClient` (depende de qual estado/município o piloto vai ocorrer)
- [ ] Configurar `ANVISA_NOTIFICATION_PROVIDER=vigimed` no `.env` de produção quando estiver pronto

> **Importante**: até esses dois clientes serem plugados, o sistema funciona em modo **mock** — útil para o piloto e para validação interna. Quando configurar `vigimed` ou `notivisa` sem o cliente plugado, o blueprint retorna **502 `notification_failed`** com mensagem clara, sem quebrar o resto do sistema.

### 4.3 F7 — Piloto regulatório (do BACKLOG_SCC)

Trabalho de produto + jurídico, não engenharia:

- [ ] F7.1 — Carta de intenção institucional para o piloto
- [ ] F7.2 — Termo de participação dos pacientes (LGPD-ready)
- [ ] F7.3 — Acordo de compartilhamento de dados com ANVISA
- [ ] F7.4 — Composição do comitê de monitoramento
- [ ] F7.5 — Implantação do piloto
- [ ] F7.6 — Documentação contínua de aprendizados
- [ ] F7.7 — Aproximação institucional (apresentações, reuniões oficiais)

---

## 5. O que você (usuário) precisa decidir/fazer manualmente

### 5.1 Próxima fase de desenvolvimento

3 caminhos possíveis pós-SCC. **Decisão sua amanhã:**

**a) F7 piloto regulatório** — fora do dev. Você precisa: parceiros institucionais, advogado, cronograma de submissão à ANVISA, paciente-piloto consentindo. Eu posso ajudar a redigir minutas, mas a execução é humana.

**b) Roadmap pré-SCC** — voltar para o que estava no `project_next_phases.md`:
- Endpoints backend faltantes (lista herdada antes do SCC)
- Migração para arquitetura de 6 agentes IA (`project_agent_architecture.md`)
- Memória persistente própria (Postgres/ChromaDB, **não** MemPalace)

**c) ADR de white-label / apps nativos** — você abriu o arquivo `docs/adr_white_label_native_apps_v1.md` na IDE hoje. Se quiser discutir essa direção, leio o ADR antes de qualquer coisa.

### 5.2 Configuração local (caso reabra a stack amanhã)

```bash
# 1. Subir DB
docker start cannabia-postgis

# 2. Subir backend (porta 5000)
env/Scripts/python.exe -m src.app

# 3. Subir frontend (porta 3001 — dev hot reload)
cd frontend && npm run dev
```

Credenciais dev (memória):
- `admin/admin123` (Admin)
- `medico/medico123` (Medico)
- `atendente/atendente123` (Atendente)
- `paciente/paciente123` (Paciente)
- Triage token: `DEV-TRIAGE-2026`

### 5.3 Validação manual no frontend (sugestão para amanhã)

Quando abrir a UI, vale exercitar os fluxos novos para ver onde a UI precisa de telas:

1. **Pharmacovigilance** — provavelmente não há tela ainda. Endpoints prontos. Decidir se a tela faz parte da próxima sprint.
2. **Regulatory reporting dashboard** — endpoints prontos. UI provavelmente também não existe ainda.
3. **Compliance overview** (`/api/v1/org/compliance/overview`) — F6.4, fechado em 2026-04-23. Aqui pode haver tela parcial.

Se a UI estiver desatualizada, a próxima sprint natural pode ser **frontend dos painéis SCC**.

### 5.4 Arquivos non-tracked no repo

Tem 4 arquivos novos que você criou e não foram commitados:

```
?? .claude/
?? docs/Dashboard Redesign.html
?? docs/Login Redesign.html
?? docs/Login.jsx
```

Como esses são experimentais (UI mockups e config local do Claude Code), deixei fora do commit. Se quiser que eu trate algum deles amanhã (revisar, integrar, descartar), me avisa.

---

## 6. Decisões arquiteturais novas desta jornada

### 6.1 F3.4 — triagem determinística, não LLM

Decisão deliberada espelhando F4.1 (`classify_response_text`): heurística regex PT-BR para auditabilidade total. LLM pode substituir mantendo a interface (`triage_adverse_event(report)` → dict com `severity_suggested/notify_required/...`). `TRIAGE_MODEL_VERSION` versiona o algoritmo para comparação cross-versões.

### 6.2 F3.5 — pure integration, sem persistência

`vigimed.py` é wrapper puro. Persistência em `pharmacovigilance_notifications` é responsabilidade do service F3.6. Isso permite testar o dispatcher sem DB e dá ao blueprint controle sobre transação/idempotência.

### 6.3 F3.5 — provider→target mapping

| ENV `ANVISA_NOTIFICATION_PROVIDER` | `notification_target` na tabela |
|---|---|
| `mock` (default) | `internal_only` |
| `vigimed` | `vigimed` |
| `notivisa` | `notivisa` |

A whitelist `internal_only` da migration 031 ganhou semântica clara: registro interno sem envio regulatório real.

### 6.4 F3.6 — orquestrador, não fachada burra

`pharmacovigilance_service.py` tem 3 casos de uso públicos com erros tipados (`AdverseEventNotFoundError`) para mapping HTTP estável (404/422/502). Blueprint é fino — toda a lógica de negócio está no service.

### 6.5 F3.6 — webhook WhatsApp NÃO usa o blueprint

Decisão: webhook chama o service direto, com auth HMAC própria. Blueprint é o painel médico/clínica autenticado. Separação clara de canais.

### 6.6 F3.7 — sem service intermediário

Padrão idêntico a `compliance.py`: blueprint read-only consulta repo direto. Funções puras (`compute_indicators_score`, `compute_overview`) são o "service light" — testáveis sem Flask nem DB.

### 6.7 F3.7 — distinção `regulatory.py` vs `regulatory_reporting.py`

`regulatory.py` (preexistente) = consulta de legislação via Google Files API.
`regulatory_reporting.py` (novo) = dashboards ANVISA sobre as 6 tabelas regulatórias.
Prefixos distintos: `/api/v1/regulatory` vs `/api/v1/regulatory-reporting`. Sem ambiguidade.

---

## 7. Estado final do SCC

| Fase | Status | Notas |
|------|--------|-------|
| Fase 0 | ✅ 2026-04-19 | integrity hardening + CI + .env + backup/DR |
| F1.1–F1.8 | ✅ 2026-04-20 | Governance Hub completo |
| F2.1–F2.5 | ✅ 2026-04-20/21 | members + traceability + hash chaining + triggers append-only |
| F3.1–F3.2 | ✅ 2026-04-20 | Schemas pharmacovigilance (031) + regulatory (032) |
| **F3.3** | ✅ 2026-04-24 | adverse_event_service |
| **F3.4** | ✅ 2026-04-24 | triage skill |
| **F3.5** | ✅ 2026-04-24 | vigimed dispatcher |
| **F3.6** | ✅ 2026-04-25 | pharmacovigilance blueprint + service |
| **F3.7** | ✅ 2026-04-25 | regulatory_reporting blueprint |
| **F3.8** | ✅ 2026-04-25 | E2E pharmacovigilance |
| F4.1–F4.7 | ✅ 2026-04-21..23 | Evidence Engine + templates + planos + dossiê + parecer + reviews |
| F5.1–F5.7 | ✅ 2026-04-20/21 | Anchoring stack completo |
| F6.1–F6.4 | ✅ 2026-04-23 | indexes + views + seed + compliance overview |
| F7.1–F7.7 | 📋 humano | piloto + parcerias |

---

## 8. Como retomar amanhã

```bash
# 1. Status do projeto
git -C c:/Users/Administrador/Desktop/Cannabia log --oneline -10

# 2. Subir stack (DB já está Up; se não estiver, docker start)
docker start cannabia-postgis
env/Scripts/python.exe -m src.app &        # backend :5000
cd frontend && npm run dev                  # frontend :3001

# 3. Suite — confirmar baseline
env/Scripts/python.exe -m pytest -q
# Esperado: 1458 passed
```

**Primeiro item da agenda de amanhã:** abrir esse `progresso23` + `MEMORY.md` + ler o ADR `docs/adr_white_label_native_apps_v1.md` que você abriu na IDE hoje. Decidir entre os 3 caminhos da seção 5.1 e abrir nova sprint.

---

**Suite:** 1458 passed, 0 failed.
**Origin/main:** sincronizado em `81671c4`.
**SCC dev puro: 100% completo.**
