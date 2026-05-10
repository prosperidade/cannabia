# Sprint 1 CannabIA — Foundation: Security + LGPD + Guardrails + Architectural Surgery

> **Status:** proposta — aguarda validação na **Fase 0** de cada track antes de qualquer commit.
> **Branch base:** `main` (Track D já mergeado, commit `f74cde9`).
> **Modelo de execução:** **multi-track paralelo** (Tracks A/B/C/D, cada um em sua branch).
> **Coordenador:** André + Claude (revisor de Fase 0 + diff + integração final).
> **Esforço estimado:** 17–21h totais distribuídos entre 4 tracks.
> **Audiência:** apresentação investidores + pré-produção com pacientes piloto + compliance LGPD.

## Contexto e motivação

Sprint 1 fecha 4 frentes simultâneas — diferente do EnjoyFun, CannabIA tem **risco de natureza clínica + LGPD** que não admite postergação:

1. **Security clássica** — secrets reais no `.env`, `SimpleConnectionPool` incompatível com multi-worker, open redirect, SECRET_KEY fallback.
2. **LGPD ATIVO** — `ai_audit_logs.input_payload`/`output_payload` (JSONB) gravam relato clínico de paciente em texto plano.
3. **Guardrails Camada 4 dead code** — `validate_output`/`sanitize_output` definidos em `guardrails.py` e nunca chamados.
4. **Architectural surgery confirmada por decisão de produto:**
   - **AgentePrescritor entra no flow principal** (Q1=a) — paciente para de receber dosagem sem rules engine + safety clamp + CYP450 matrix.
   - **MemPalace path extirpado** (Q2=remover) — fim do dead code com classificação interna de "fraude".
   - **`ai_prompt_versions` adiado pra Sprint 2** (Q3=b).

## Princípios inegociáveis (todos os tracks)

1. **Read-then-act.** Phase 0 obrigatória em cada track. Não modifique código até receber sinal verde do coordenador.
2. **Evidência ou nada.** Toda decisão referencia arquivo:linha. Sem evidência → vira pergunta na Phase 0.
3. **Branches isoladas.** Cada track trabalha em sua branch. Zero merge entre tracks até integração final.
4. **Critério de sucesso verificável.** Cada tarefa tem teste/smoke/comando concreto.
5. **Lint/typecheck limpos** nos arquivos tocados.
6. **Commit message padrão:** `feat(sprint-1-{track}-{tarefa}): descrição curta`.

## Não-objetivos (Sprint 1)

- ❌ Plugar `prompt_registry` + `ai_prompt_versions` (Sprint 2).
- ❌ Gateway central de LLM (Sprint 3).
- ❌ Evaluation harness com golden corpus (Sprint 4).
- ❌ Paginação LIMIT/OFFSET no banco (Sprint 2).
- ❌ God objects refactor.
- ❌ Multi-tenant RLS no PostgreSQL.
- ❌ Skills como Forma B.
- ❌ Auditar TODOS os 100+ `except Exception` — top 20 mais críticos vão pro Track D; resto Sprint 2.

## Pré-condições (todos os tracks)

- [ ] `main` em estado verde, último commit `f74cde9` ou posterior.
- [ ] Working tree limpo.
- [ ] Acesso ao Render dashboard (rotação de keys + ambiente var management).
- [ ] Confirmação: as keys atuais em `.env` (OpenAI, Google, Meta WhatsApp) podem ser rotacionadas hoje sem quebrar produção.

---

## Track A — Security + LGPD critical (~6-7h)

> **Objetivo:** fechar bloqueadores de security clássica + corrigir exposição LGPD em audit logs.
> **Branch:** `feat/sprint-1-A-security-lgpd`
> **Sub-agente:** A.

### Phase 0 — Track A

**Step 1 — Leia (Track A apenas):**

- `.env` (local de dev — confirmar quais keys aparecem no repo, prefixos, mtime)
- `.env.example` (template oficial)
- `src/config.py:25` (SECRET_KEY fallback principal — alvo de A.4)
- `src/app.py:104` (segundo fallback inline `SECRET_KEY or "dev-secret-key-fallback"` — alvo de A.4; ver Q-A3)
- `src/infra/crypto.py:30` (terceiro fallback, seed HKDF se ENCRYPTION_KEY ausente — alvo de A.4; ver Q-A3 + comentário em `crypto.py:52`)
- `src/infra/database.py:38` (SimpleConnectionPool atual)
- `src/app.py:273-274` (linha 273: `next_url = request.args.get("next")`; linha 274: o redirect propriamente)
- `src/ai/service.py:168-189` (bloco `save_ai_audit_log`; linha 174 `input_payload`; linha **175** `output_payload`)
- `src/ai/memory.py:54-60` (`_sanitize_pii` existente — regex-based, escrita para MemPalace)
- `src/repositories/ai_audit_repository.py` (estrutura da função `save_ai_audit_log`)
- Schema `ai_audit_logs` — confirmar tipo das colunas `input_payload` e `output_payload` (esperado: JSONB)
- Schemas de `patients`, `medical_history`, e qualquer tabela referenciada via `grep -rn "input_payload\|output_payload" src/` para entender o que vai pro JSONB
- `requirements.txt` (verificar versão psycopg2 — confirmar `ThreadedConnectionPool` disponível)
- `render.yaml` (entender como envs chegam ao Render — produção usa env vars do Render dashboard, NÃO `.env.production` no repo)

**Step 2 — Reporte (4 blocos):**

**(a) Divergências:**
- `.env` local: quais keys aparecem (prefixo + últimos 4 chars) e mtime do arquivo. Cruzar com memória de rotação 2026-04-27.
- Em produção, as keys vivem no Render dashboard — Phase 0 não acessa Render. Apenas listar o que precisa rotacionar.
- `_sanitize_pii` em `memory.py:54` é regex-based (escrita pra MemPalace, texto livre). Para `ai_audit_logs.input_payload/output_payload` que é **JSONB estruturado**, regex em string serializada é a abordagem errada — corrompe estrutura. Ver pergunta numerada Q-A1.
- `next_url` em `src/app.py:273-274`: 273 é a leitura do GET param, 274 é o redirect. A.4 valida next_url entre as 2 linhas.
- **`SECRET_KEY` fallback aparece em 3 pontos** (não 1): `config.py:25`, `app.py:104` (inline), `crypto.py:30` (seed HKDF). Ver Q-A3.

**(b) Confirmações:**
- `ThreadedConnectionPool` é drop-in replacement do `SimpleConnectionPool` (mesma assinatura).
- Render aceita env vars via dashboard.
- `next_url` validation: regex `^/[a-zA-Z0-9_/-]*$` ou check sequencial (`startswith('/')` + sem `://` + sem `\\`)? Padrão da indústria é o segundo.
- `.env.production` não existe no repo (confirmar) — produção usa Render dashboard.

**(c) Riscos arquiteturais:**
- **Rotação de keys em produção** exige janela curta (~5min). Phase 0 não rotaciona.
- **PII redaction só forward.** Logs antigos com PII viram dívida explícita pra purge separado (Sprint 2 + retention policy). Documentar em `docs/BACKLOG_LGPD.md`.
- **Estratégia de PII redaction (CRÍTICO):** ver Q-A1 abaixo.
- **`SECRET_KEY` como seed de criptografia (CRÍTICO):** `crypto.py:30+52` usa `SECRET_KEY` como base de HKDF se `ENCRYPTION_KEY` não definida. Fallback `dev-secret-key-fallback` público vira chave de cripto pública conhecida — vulnerabilidade séria. Ver Q-A3.

**(d) Proposta:**
- Ordem: A.2 (pool fix, isolado) → A.4 (next_url + SECRET_KEY) → A.3 (PII redaction, mais elaborado) → A.1 (rotação de keys, último porque exige janela).

**Step 3 — Perguntas em aberto** (numeradas, com impacto explícito).

**Q-A1 (CRÍTICA): Estratégia de PII redaction em `ai_audit_logs.input_payload/output_payload`**

`_sanitize_pii` existente em `memory.py:54` é regex-based e foi escrita para MemPalace (texto livre). Memória do projeto marca MemPalace como descartado (2026-04-24). Track C vai extirpar MemPalace path completamente.

`ai_audit_logs.input_payload`/`output_payload` são **JSONB** — dados estruturados (ex: `{"patient_data": {"name": "João", "cpf": "..."}, "treatment_plan": {...}}`). Regex em JSON serializado pode corromper estrutura.

Decida entre:

- **(a)** Construir **novo sanitizador estrutural** `_sanitize_clinical_payload(payload: dict) -> dict` em arquivo apropriado (ex: `src/ai/audit_redaction.py`). Walk recursivo do dict, redact value por **key pattern** (keys que matcham lista de campos sensíveis: `name`, `cpf`, `rg`, `email`, `phone`, `address`, `dob`, `medical_history`, `allergies`, `medications`, etc.). Adicional: aplicar regex em string-leaves não-pegas por key (catch CPF/phone em campos free-text). `_sanitize_pii` antigo continua existindo — Track C decide se remove com MemPalace.

- **(b)** Estender `_sanitize_pii` regex-based pra cobrir JSONB. Aplicar `json.dumps(payload)` → regex → `json.loads`. **Risco:** corromper structure se padrão substituído estiver em chave/valor com escape. Não recomendado.

- **(c)** Híbrido: estrutural por key + regex-em-string-leaves dentro do mesmo helper. Mais robusto que (a) puro.

**Recomendação:** (a) ou (c). Sub-agente reporta na Phase 0 qual estratégia propõe e o coordenador valida antes de implementar.

**Q-A2: Lista exaustiva de campos PII a redact**

A partir do schema de `patients`, `medical_history`, e demais tabelas que alimentam `input_payload`/`output_payload`. Sub-agente propõe lista com path:linha de cada campo. Considerar:

- Identificadores: nome, CPF, RG, email, phone, endereço, data de nascimento.
- Clínicos: queixa principal, medicações em uso, alergias, histórico clínico, comorbidades, exames anteriores, anamnese livre.
- Profissionais: identificação do médico responsável, CRM, conselho regional.
- Outros campos clínicos específicos do CannabIA que aparecerem nos schemas.

**Q-A3 (CRÍTICA): Estratégia de SECRET_KEY failsafe (3 pontos simultâneos)**

`SECRET_KEY` com fallback `"dev-secret-key-fallback"` aparece em **3 pontos**, não 1:

1. `src/config.py:25` — fallback principal.
2. `src/app.py:104` — `app.config["SECRET_KEY"] = SECRET_KEY or "dev-secret-key-fallback"` (fallback inline secundário).
3. `src/infra/crypto.py:30` — usado como seed HKDF se `ENCRYPTION_KEY` não definida (ver comentário em `crypto.py:52`).

Se A.4 só consertar `config.py:25`, sobram 2 pontos onde a string fallback aceita produção sem `SECRET_KEY` setada. Pior: `crypto.py` usa `SECRET_KEY` como seed de chave de criptografia — fallback público conhecido = vulnerabilidade séria.

Decida entre:

- **(a) Sempre raise:** `if not SECRET_KEY: raise RuntimeError("SECRET_KEY env var required")` aplicado nos 3 pontos. Dev é forçado a setar em `.env`. Mais limpo, mas friction inicial.

- **(b) Random in-memory em dev:** se `FLASK_ENV != "production"` e `SECRET_KEY` ausente, gera `secrets.token_hex(32)` em memória. Imprime warning. Dev funciona out-of-the-box; cookies invalidam a cada restart.

- **(c) Híbrido com FLASK_ENV:** raise em produção (hard); random in-memory + warning em dev. Mais seguro que (b), menos friction que (a).

**Recomendação:** (c).

A.4 deve aplicar a estratégia escolhida nos **3 pontos simultaneamente** — sugestão: extrair função utilitária em `src/config.py` (ex: `_get_secret_key_or_fail()`) consumida por `app.py:104` e `crypto.py:30`. Em `crypto.py:30+52`, adicionar comentário explícito que `SECRET_KEY` como seed de cripto **só é aceitável em dev**; produção deve exigir `ENCRYPTION_KEY` separada.

Sub-agente reporta na Phase 0 qual estratégia propõe e o coordenador valida antes de implementar A.4.

**Step 4 — PARE.** Aguarde sinal verde do coordenador.

### Tarefas — Track A

**A.2 — `SimpleConnectionPool` → `ThreadedConnectionPool`** (~30min)
- Em `src/infra/database.py:38`, trocar `SimpleConnectionPool` por `ThreadedConnectionPool`.
- Adicionar teste em `tests/test_database_pool.py` simulando conexões concorrentes.
- **Critério:** teste verde + `gunicorn` startup OK em local.

**A.3 — Sanitizar PII em `ai_audit_logs`** (~2-3h)
- Implementar estratégia decidida em Q-A1 (recomendação coordenador: opção (a) ou (c)).
- Criar arquivo apropriado (sugestão: `src/ai/audit_redaction.py`) com `sanitize_clinical_payload(payload: dict) -> dict`.
- Em `src/ai/service.py:174-175`, aplicar `sanitize_clinical_payload(input_payload)` e `sanitize_clinical_payload(output_payload)` antes de `save_ai_audit_log`.
- Adicionar teste com fixture clínico realista — verificar que após save, query no `ai_audit_logs` não revela PII em chaves sensíveis.
- Documentar comportamento "só forward" em `docs/BACKLOG_LGPD.md` (criar arquivo) — logs anteriores ficam como dívida pra Sprint 2 + retention policy.
- **Critério:** teste verde + smoke real fazendo `process_patient_case` e inspecionando registro no DB.

**A.4 — Hardening básico** (~1.5-2h, expandido pra 3 pontos de SECRET_KEY)
- Em `src/app.py:273-274`, validar `next_url` entre a leitura do GET param e o redirect: deve começar com `/` E não conter `://` E não conter `\\`. Caso contrário, redirect pra `/`.
- Implementar estratégia decidida em Q-A3 nos **3 pontos simultaneamente**:
  - `src/config.py:25` — fallback principal.
  - `src/app.py:104` — fallback inline secundário.
  - `src/infra/crypto.py:30` — seed HKDF se `ENCRYPTION_KEY` ausente.
- Sugestão: extrair `_get_secret_key_or_fail()` em `src/config.py` consumido pelos 3 callers. Em `crypto.py:30+52`, adicionar comentário explícito que `SECRET_KEY` como seed de cripto **só é aceitável em dev**; produção deve exigir `ENCRYPTION_KEY` separada.
- Adicionar 3 testes pequenos: open redirect bloqueado; SECRET_KEY ausente em prod → app falha startup; SECRET_KEY ausente em dev → app inicia com warning + chave random.
- **Critério:** testes verdes; app local sem `SECRET_KEY` em modo dev funciona com warning; app em modo produção falha com mensagem útil.

**A.1 — Rotação de keys** (~2h, exige janela)
- **PRÉ-REQUISITO:** confirmar com André quais keys rotacionar e horário da janela.
- Rotacionar OpenAI + Google + Meta WhatsApp via Render dashboard (NÃO no `.env` do repo).
- Atualizar variável correspondente no Render.
- Revogar keys antigas.
- Documentar em `docs/SECRETS_MANAGEMENT.md` (criar) o processo: "secrets vivem no Render dashboard, nunca em arquivo local."
- **Critério:** produção responde (smoke `/api/v1/health` + 1 chat real); chamadas com keys antigas falham com 401.

### Pausas — Track A

- **Antes de A.3:** confirmar com coordenador estratégia Q-A1 (a/b/c) + lista exata de campos pra sanitizar (Q-A2).
- **Antes de A.1:** PAUSA OBRIGATÓRIA — coordenador autoriza janela de manutenção + confirma que Render env vars já estão prontos.
- **Após A.1:** smoke completo em produção antes de fechar PR.

### Encerramento — Track A

PR com:
- Sumário das 4 sub-tarefas + critério de sucesso atingido em cada.
- `docs/sprints/sprint_1_A.md` com decisões da Phase 0 (estratégia PII, lista de campos).
- Confirmação que keys foram rotacionadas (datas, sem expor as novas keys).
- `docs/BACKLOG_LGPD.md` registrado como dívida (purge de logs antigos).

---

## Track B — Guardrails + Cost honesto (~3-4h)

> **Objetivo:** plugar Camada 4 de guardrails (dead code → vivo), corrigir pricing.py pra não subnotificar custo Gemini, popular timings_ms que ficam NULL hoje.
> **Branch:** `feat/sprint-1-B-guardrails-cost`
> **Sub-agente:** B.

[Track B continua igual ao prompt original — tarefas B.1, B.2, B.3 com mesmas decisões e ordem]

### Phase 0 — Track B

(Igual ao original; ler `guardrails.py`, `service.py:191`, `pricing.py`, `clinical_flow.py`, `chains.py`, `ai_audit_repository.py`)

### Tarefas — Track B

**B.3 — Popular `timings_ms`** (~30min-1h, isolado, pode arrancar primeiro)
**B.2 — Pricing Gemini + cost por stage** (~2-2.5h, expansão de escopo aprovada)
**B.1 — Plugar Camada 4 com helper recursivo** (~1-1.5h)

### Encerramento — Track B

PR com sumário + testes + `docs/sprints/sprint_1_B.md` com aviso pro Track C: `clinical_flow.py` retorna `timings_ms` extensível.

---

## Track C — Architectural Surgery (~5-7h)

> **Objetivo:** executar 2 cirurgias arquiteturais decididas — AgentePrescritor entra no flow principal + MemPalace path completamente extirpado.
> **Branch:** `feat/sprint-1-C-arch-surgery`
> **Sub-agente:** C.
> **Track C tem mais risco que os outros 3.** Phase 0 mais profunda. Pausa obrigatória entre C.2 e C.1.

[Track C continua igual ao prompt original — Phase 0 com sub-leituras C.1 e C.2; tarefas C.2 (extirpar MemPalace) → C.1 (Prescritor no flow) → C.3 (doc dívida)]

⚠️ **Quando Track C abrir:** precisa fazer `git fetch && git checkout main && git pull` antes de criar branch — Track D mergeou em main e tocou `src/ai/agents/cientifico.py:53` (área diferente da que C vai mexer em :170-194, mas vale rebase pra evitar surpresa).

⚠️ **Coordenação com `_sanitize_pii`:** Track A vai criar novo sanitizador estrutural (Q-A1). Track C extirpa MemPalace path. Decisão: `_sanitize_pii` regex-based fica órfão após Track A — Track C deve removê-lo junto com a extirpação do MemPalace path se não houver outro consumer (verificar via `grep -rn "_sanitize_pii"`).

---

## Track D — Tactical hardening (~3h) ✅ MERGEADO

Track D foi mergeado em main no commit `f74cde9`. Detalhes em `docs/sprints/sprint_1_D.md`.

---

## Sequenciamento e integração final

```
Phase 0 (Tracks A, B em paralelo agora)
  ↓
Coordenador revê reports + responde perguntas
  ↓
Sinal verde por track
  ↓
Tracks A, B executam em paralelo (branches isoladas)
  ↓
A mergea, B mergea (ordem: D → A → B; D já feito)
  ↓
Track C abre com main atualizada (D + A + B dentro)
  ↓
C faz Phase 0, executa com 2 pausas internas, mergea
  ↓
[INTEGRAÇÃO] smoke completo em main
  ↓
Sumário consolidado Sprint 1 + atualização docs/progresso27.md
```

## Coordenador

O coordenador (André + Claude na conversa principal):

1. **Phase 0:** lê reports estruturados. Responde perguntas. Sinal verde por track.
2. **Durante execução:** disponível pra dúvidas. Track C tem 2 PAUSAS OBRIGATÓRIAS.
3. **PR review:** diff + testes + docs por PR. Sinal verde pro merge.
4. **Pós-merge integração:** smoke completo em main.

## Encerramento da Sprint 1

Quando todos os 4 tracks tiverem mergeados:

1. Atualize `docs/progresso27.md` com seção "Sprint 1 CannabIA".
2. Crie `docs/sprints/sprint_1_consolidado.md` com:
   - Sumário das 4 tracks.
   - Decisões arquiteturais (especialmente C.1 Prescritor + C.2 MemPalace extirpado + A.3 estratégia PII).
   - Dívidas registradas pra Sprints 2-4.
   - Próximo passo: Sprint 2 (plugar prompt_registry + paginação + Sentry).
3. Sumário final:

```markdown
**CannabIA — Sprint 1 fechada.**

X commits across 4 branches, Y testes adicionados, Z linhas net.
Track A (security+LGPD): pool fix, PII redaction estrutural em audit logs, keys rotacionadas, hardening.
Track B (guardrails+cost): Camada 4 viva, Gemini pricing + cost por stage, timings_ms populado.
Track C (architectural surgery): Prescritor no flow + MemPalace 100% extirpado.
Track D (tactical): webhooks 501, logging em 20 except críticos, --cov no CI, staging backlog.

Próximo: Sprint 2 — plugar prompt_registry + paginação LIMIT/OFFSET + Sentry.
```
