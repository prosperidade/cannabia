# Relatório de Auditoria — Subsistema de Agentes IA — Cannab'IA

**Data:** 2026-05-09
**Branch / commit:** main / 3c78859
**Relatório de sistema referenciado:** `auditoria/RELATORIO_SISTEMA.md` (paralelo, não consultado nesta sessão para evitar duplicação)
**Solicitante:** prosperidade (vovoprogramador2024@gmail.com)

> **Legenda de evidência:** 🔴 confirmado em código / 🟡 provável (precisa confirmação cruzada) / 🟢 hipótese / **PRECISA CONFIRMAÇÃO HUMANA** quando não dá pra concluir só pelo repo.

---

## Sumário executivo

- **Maturidade do subsistema de IA: 5/10.** Fundação sólida (Pydantic em todas as etapas, circuit breaker por provider, failover OpenAI↔Gemini, structured output forçado via function_calling, guardrails de input em 4 camadas, billing por tenant). Mas **observabilidade de custo está parcialmente quebrada**, **PII vai pro audit log sem redaction**, **a 4ª camada de guardrails é dead code**, **prompt versioning existe na infra mas não está plugado**, e **não há evaluation harness** — só testes unitários com mock. O sistema funciona; a confiança em produção em escala depende de fechar essas lacunas.

- **Pronto para escala? 🟡 Amarelo.** Roda hoje, mas três coisas vão morder em produção: (a) custo subnotificado quando RAG usa Gemini, (b) compliance LGPD do `ai_audit_logs.input_payload` sem redação, (c) ausência de cost cap por job — runaway pode estourar tenant.

- **Top 3 problemas críticos:**
  1. 🔴 `validate_output`/`sanitize_output` definidos mas **nunca chamados** — output do LLM vai cru ao paciente sem a Camada 4 de guardrails.
  2. 🔴 `ai_audit_logs.input_payload`/`output_payload` (JSONB) gravam o relato clínico completo do paciente sem redaction — LGPD risk.
  3. 🔴 Pricing table só conhece `gpt-4o-mini`; relatório científico via Gemini grava `estimated_cost_usd=0` — métrica de custo está sistematicamente subestimada.

- **Top 3 oportunidades:**
  1. Plugar `prompt_registry.py` + tabela `ai_prompt_versions` no `service.py` (hoje `prompt_version="v1.0"` é hardcoded em [service.py:45](src/ai/service.py#L45)).
  2. Criar `ai_evaluation_baseline.json` com 30-50 casos clínicos de referência e rodar em CI a cada PR que toque `src/ai/**`.
  3. Introduzir gateway central (`src/ai/llm_gateway.py`) com cost cap por job + tracking unificado de tokens — chains.py hoje fala direto com OpenAI/Gemini SDK.

---

## 1. Inventário de agentes

| Agente | Path | Purpose | Estado | Uso |
|---|---|---|---|---|
| Triagem | [src/ai/agents/triagem.py](src/ai/agents/triagem.py) | Extrai patologias do relato livre + escolhe widget | 🔴 produção | Webhook WhatsApp / chat web — ponto de entrada B2B2C |
| Anamnese | [src/ai/agents/anamnese.py](src/ai/agents/anamnese.py) | Análise clínica estruturada (CID-10, risk_level) | 🔴 produção | Etapa 1 do `SpecialistClinicalFlow` |
| Tratamento | [src/ai/agents/tratamento.py](src/ai/agents/tratamento.py) | Plano terapêutico inicial CBD:THC | 🔴 produção | Etapa 2 do `SpecialistClinicalFlow` |
| Científico | [src/ai/agents/cientifico.py](src/ai/agents/cientifico.py) | Relatório com RAG ChromaDB + auto-ingest PubMed (C6) | 🔴 produção | Etapa 3 do `SpecialistClinicalFlow` |
| Prescritor | [src/ai/agents/prescritor.py](src/ai/agents/prescritor.py) | Dosagem com rules engine + LLM + safety clamp (CYP450) | 🟡 prod parcial | Endpoint dedicado; **não está no flow principal** |
| Extrator | [src/ai/agents/extrator.py](src/ai/agents/extrator.py) | PubMed search + ingest ChromaDB + monitor de bases | 🔴 produção | Pipeline batch / monitores; **não está no flow principal** |
| Regulatório | [src/ai/agents/regulatorio.py](src/ai/agents/regulatorio.py) | ANVISA, sandbox eligibility, triage adverse event (F3.4) | 🔴 produção | Endpoints regulatorios + farmacovigilância |
| Follow-up | [src/ai/agents/follow_up.py](src/ai/agents/follow_up.py) | Mensageria pós-consulta (D+3, D+7, D+15) | 🟡 dev | Schedule jobs — **PRECISA CONFIRMAÇÃO HUMANA** sobre se está rodando em prod |
| Orchestrator | [src/ai/agents/orchestrator.py](src/ai/agents/orchestrator.py) | Chain manager genérico (sequential com input_map) | 🟡 dev | Existe mas o flow real ([clinical_flow.py:17-104](src/ai/clinical_flow.py#L17-L104)) **não usa o Orchestrator** — chama agentes diretamente. Código de orchestration está duplicado. |

**Total: 8 agentes + 1 orchestrator (sub-utilizado).** Total de 4.439 linhas em `src/ai/`. Maior agente: Extrator (718 linhas).

---

## 2. Stack de IA

- **Providers:**
  - OpenAI — `gpt-4o-mini` (todas as etapas via function_calling em triagem; chat completions com temperature=0 nas demais).
  - Google Gemini — `gemini-1.5-flash` (relatório RAG quando ChromaDB tem chunks; failover do triage).
  - **Sem Anthropic** — `import anthropic` não aparece em src/. Dependência apenas no Cannab'IA repo via Claude Code (este chat), não no produto.

- **SDKs:** `openai`, `google.genai`, `chromadb`, `tenacity` (retry exponencial). `requirements.txt` declara as três famílias.

- **Gateway / wrapper central:** **não existe.** Cada chain em [chains.py](src/ai/chains.py) instancia `OpenAI()` ou `genai.Client()` no top-level do módulo. `pricing.calculate_cost()` é chamado pelo `service.py` ao final, mas não há ponto único que pega *toda* chamada LLM antes de despachar.

- **Cost cap:**
  - 🟡 Por tenant: existe via `billing_service.check_ai_allowance()` ([service.py:55](src/ai/service.py#L55)) — count-based + tokens-based; bloqueia ANTES via `BillingLimitExceeded` se o plano estourou.
  - 🔴 Por job: **inexistente.** Um job que ficar travado em retries pode consumir 3 retries × 3 stages × ~30s = ~5 min sem teto de tokens.
  - 🔴 Global / app-wide: não encontrei nenhuma config tipo `MAX_DAILY_AI_SPEND_USD`.

- **Resiliência:** circuit breaker thread-safe por provider em [chains.py:78-160](src/ai/chains.py#L78-L160) (3 estados, 5 falhas → OPEN, 60s recovery). Retry tenacity com backoff exponencial 2-16s. Timeout OpenAI 30s, Gemini 45s — vindos de `OPENAI_TIMEOUT`/`GEMINI_TIMEOUT`.

---

## 3. Deep dive por agente

### 3.1 Agente: Triagem ([src/ai/agents/triagem.py](src/ai/agents/triagem.py))

**Estrutura:** 82 linhas. `AgenteTriagem(BaseAgent)` com 2 skills (`extract_conditions`, `detect_red_flags`). É um wrapper fino sobre `chains.run_triage_agent()` ([chains.py:484-544](src/ai/chains.py#L484-L544)).

**System prompt:** `TRIAGE_AGENT_SYSTEM_PROMPT` em [prompts.py:5-130](src/ai/prompts.py#L5-L130) — **130 linhas** (🟡 amarelo segundo Anthropic; >80 já é vermelho). Carrega: identidade + missão + catálogo dos 10 widgets + regras clínicas + regras de seleção de widget + regras de mensagem + restrições de segurança + contexto runtime. **Forma A pura** (tudo no prompt).

**Tools:**
- `TRIAGE_TOOL_DEFINITION` ([schemas.py:108-180](src/ai/schemas.py#L108-L180)) — function_calling OpenAI com `tool_choice: required`. ✅ Schema rigoroso, com exemplos por tipo de widget na description, enums em `inject_widget` e `confidence`.
- `TRIAGE_GEMINI_SCHEMA` ([schemas.py:185-…](src/ai/schemas.py#L185)) — espelho para Gemini `response_schema`. Pequena divergência: Gemini não suporta `enum` em todos os campos, então `data` fica como `{"type": "object"}` aberto.

**Context / memory:** `prior_context` injetado por kwarg ([chains.py:489](src/ai/chains.py#L489)) — sem compactação. Se o histórico for longo, vai cru pro prompt. `BaseAgent.run()` faz `recall_memory()` via MemPalace fire-and-forget, mas memory_query precisa ser passado explicitamente; triagem não passa.

**Quality / evaluation:** [tests/test_triage_routes.py](tests/test_triage_routes.py), [tests/test_triage_intake_service.py](tests/test_triage_intake_service.py), [tests/test_triage_link_service.py](tests/test_triage_link_service.py) — testam o fluxo HTTP / service, não o agente. **Sem teste com LLM real** sobre extração de patologias / escolha de widget. **Sem golden set**.

**Observabilidade:** `logger.info("Triage concluído: widget=%s, conditions=%d, tokens=%d", …)` em [chains.py:537-542](src/ai/chains.py#L537-L542). Tokens vão para `ai_audit_logs` via service.py. Mas o triage agent é chamado de webhook WhatsApp e **não passa por `CannabIAService.process_patient_case`** (esse serviço é só para o flow Anamnese→Tratamento→Cientifico). Então **PRECISA CONFIRMAÇÃO HUMANA** se chamadas de triagem geram entrada em `ai_audit_logs`.

**Multi-tenant:** `clinic_id` é parâmetro do `run_triage_agent`. ✅

**Confidence semântico ambíguo:** [triagem.py:80](src/ai/agents/triagem.py#L80) — `confidence=0.95 if has_red_flags else 0.85`. "Confidence" aqui parece misturar "certeza do modelo" com "urgência clínica". Não é bug funcional, mas vai confundir downstream que consume o campo.

---

### 3.2 Agente: Anamnese ([src/ai/agents/anamnese.py](src/ai/agents/anamnese.py))

**Estrutura:** 67 linhas. Wrapper fino sobre `run_clinical_analysis()`. Output: `ClinicalAnalysis` (probable_conditions, risk_level, recommended_exams, red_flags).

**System prompt:** `ANAMNESIS_PROMPT` em [prompts.py:137-166](src/ai/prompts.py#L137-L166) — **30 linhas, lean** ✅. Estrutura JSON estrita + 7 campos do paciente.

**Tools:** Nenhum function_calling. Usa `_run_and_validate` ([chains.py:220-235](src/ai/chains.py#L220-L235)) — JSON puro, parse + ValidationError. Sem fallback Gemini para essa etapa (só OpenAI).

**Context / memory:** `_memory_context` recebe `search_results` da memória se houver, e injeta em `patient_data["_similar_cases"]` ([anamnese.py:48-49](src/ai/agents/anamnese.py#L48-L49)). 🟡 Mas `_run_and_validate` não usa esse campo no prompt — `ANAMNESIS_PROMPT` não tem `{_similar_cases}` na template. **Bug latente**: a recall acontece, é injetada no kwarg, e o LLM nunca vê.

**Quality / evaluation:** Sem teste dedicado. Coberto indiretamente em `test_clinical_flow.py` se existir — **PRECISA CONFIRMAÇÃO HUMANA** (não encontrei `test_anamnese*` listado).

**Observabilidade:** Mesmo pipeline que o flow geral.

**Multi-tenant:** OK via `g.clinic_id`.

---

### 3.3 Agente: Tratamento ([src/ai/agents/tratamento.py](src/ai/agents/tratamento.py))

**Estrutura:** 49 linhas — o mais fino do flow. Apenas chama `run_treatment_plan(clinical_analysis)`.

**System prompt:** `TREATMENT_PLAN_PROMPT` ([prompts.py:169-192](src/ai/prompts.py#L169-L192)) — **24 linhas** ✅.

**Tools:** Nenhum.

**Context / memory:** Não usa `_memory_context`. Recebe só `clinical_analysis`.

**Quality / evaluation:** Nada dedicado.

**Risco clínico relevante:** O `TREATMENT_PLAN_PROMPT` é genérico — `cannabinoid_ratio`, `suggested_dosage`, `administration_route` como strings livres. Não há guardrail de dosagem aqui (existe, sim, no Prescritor — mas o Prescritor não está no flow). 🔴 **No flow real (Anamnese→Tratamento→Cientifico) o paciente recebe uma dosagem sem o rules engine + safety clamp do AgentePrescritor.** Decisão arquitetural a confirmar com humano.

---

### 3.4 Agente: Científico ([src/ai/agents/cientifico.py](src/ai/agents/cientifico.py))

**Estrutura:** 249 linhas. 3 skills: `search_evidence`, `auto_ingest_evidence`, `generate_report`. Executa C6 (PubMed auto-ingest em atendimento) — quando RAG retorna 0 chunks, busca PubMed em tempo real, registra em `knowledge_catalog`, ingere abstracts no ChromaDB, refaz busca, gera relatório. Commit `b2019bc`.

**System prompts:**
- `SCIENTIFIC_REPORT_PROMPT` ([prompts.py:195-214](src/ai/prompts.py#L195-L214)) — 20 linhas ✅
- `SCIENTIFIC_REPORT_RAG_PROMPT` ([prompts.py:217-244](src/ai/prompts.py#L217-L244)) — 28 linhas ✅

**Tools:** Sem function_calling. Gemini com `response_mime_type=application/json`. Failover Gemini→OpenAI quando circuit aberto ([chains.py:354-360](src/ai/chains.py#L354-L360)).

**Context / memory:** Constrói query a partir de `_memory_context.query` ou campos do treatment_plan ([cientifico.py:170-194](src/ai/agents/cientifico.py#L170-L194)) — bem feito, evita serializar o dict inteiro como query.

**Quality / evaluation:** [tests/test_cientifico_auto_ingest.py](tests/test_cientifico_auto_ingest.py) — 7+ testes cobrindo skip/trigger/disabled/empty/dedup. ✅ Boa cobertura para o caminho C6, mas **mockada** (não testa qualidade do relatório).

**Observabilidade:** `logger.info("Gemini RAG report gerado: %d tokens (contexto: %d chunks).", ...)` em [chains.py:372-376](src/ai/chains.py#L372-L376). ✅

**Multi-tenant:** `created_by` propaga; `register_to_knowledge_base` usa dedup por DOI. 🟢 Mas o `knowledge_catalog` é **global** (não tem `clinic_id`) — cada artigo encontrado por uma clínica fica disponível para todas. Pode ser intencional (Memory Project: "C7 - agregacao clinica anonimizada"). **PRECISA CONFIRMAÇÃO HUMANA**.

**Confidence:** [cientifico.py:247](src/ai/agents/cientifico.py#L247) — `0.85 if rag_used else 0.7`. Razoável.

---

### 3.5 Agente: Prescritor ([src/ai/agents/prescritor.py](src/ai/agents/prescritor.py))

**Estrutura:** 86 linhas. 3 skills: safety_limits (rules engine determinístico), calculate_dosage (rules + LLM + safety clamp), check_interactions (CYP450 matrix). Lógica real está em [src/ai/prescriber.py](src/ai/prescriber.py) (113 linhas). O agente é wrapper.

**System prompt:** `PRESCRIBER_SYSTEM_PROMPT` em [prompts.py:252-353](src/ai/prompts.py#L252-L353) — **101 linhas, 🔴 VERMELHO** segundo Anthropic (>80). Carrega: missão + 5 regras farmacológicas invioláveis + protocolo de titulação + interações CYP450 + contraindicações + regras anti-alucinação + tabela de referência por 11 condições + contexto runtime. Excelente conteúdo clínico, **mas tudo num único string** — manutenção difícil; mudança em uma regra exige reler 100 linhas.

**Tools:** Function calling forçado (`recommend_dosage` — mencionado no prompt mas tool definition em outro arquivo — **PRECISA CONFIRMAÇÃO HUMANA**: não encontrei `RECOMMEND_DOSAGE_TOOL_DEFINITION` no schemas.py; pode estar em `src/ai/prescriber.py`).

**Context / memory:** `_memory_context` consultado para buscar prescrições similares.

**Quality:** Sem teste dedicado encontrado para `prescritor.py`. **Risco clínico alto**.

**Observabilidade:** `logger.warning("Prescriber LLM falhou (retry automático)")` — sim. Token tracking — sim, via skill.

---

### 3.6 Agente: Regulatório ([src/ai/agents/regulatorio.py](src/ai/agents/regulatorio.py))

**Estrutura:** 460 linhas. 5 skills: check_anvisa, query_legislation, check_sandbox_eligibility, triage_adverse_event, … (4ª e 5ª implementadas). Commits recentes: `4a01f23` (sandbox eligibility), `d83c3f0` (triage adverse event).

**Quality:** [tests/test_agente_regulatorio.py](tests/test_agente_regulatorio.py) — cobertura forte, ~15 testes. ✅ Melhor coberto que o flow clínico.

**Observabilidade:** Mock-based — não chama LLM real nos testes.

---

## 4. Análise transversal

### 4.1 Tools no geral

🔴 **Não existe registry global de tools.** O que o projeto tem são *skills* registradas por agente via `BaseAgent.register_skill()` ([base.py:81-90](src/ai/agents/base.py#L81-L90)). Cada agente tem 1-5 skills. Skills NÃO são apresentadas ao LLM como tools — são métodos Python que o código chama. O único uso real de "tool" no sentido Anthropic/OpenAI (function_calling) é:
- `TRIAGE_TOOL_DEFINITION` (1 tool, schema rico).
- `recommend_dosage` no prescriber (function_calling forçado, mas tool definition não localizado claramente).

**Avaliação Anthropic-style ("5 tools bem desenhadas > 20 sobrepostas"):**
- 🟢 Em quantidade está OK: 1-2 tools formais.
- 🟡 Em qualidade: o `TRIAGE_TOOL_DEFINITION` é exemplar — description com exemplos por widget, enums, required fields. Bom referência para futuras tools.
- 🔴 **Skills são confusas com tools no diário/log**: `result.skills_used` ([base.py:55](src/ai/agents/base.py#L55)) lista nomes de skills, e a documentação fala em "tool calls trackeados" — mas LLM não chama skills, só código Python. Documentação interna mistura conceitos.

### 4.2 Skills / domain knowledge

🔴 **Forma A dominante.** `PRESCRIBER_SYSTEM_PROMPT` (101 linhas) e `TRIAGE_AGENT_SYSTEM_PROMPT` (130 linhas) carregam catálogos completos no prompt — 11 condições terapêuticas, 10 widgets, 5 regras farmacológicas, 5 interações CYP450. Sintomas:
- 🟡 Repetição: regras de "responda apenas JSON puro" aparecem em 4 prompts.
- 🟡 Manutenção difícil: editar a tabela CBD:THC por condição exige editar string Python; sem versão semântica.
- 🔴 **`prompt_registry.py` e `ai_prompt_versions` (tabela) existem para resolver exatamente isso** — mas não estão plugados. `service.py:45` hardcoda `prompt_version="v1.0"`. Capacidade de hot-swap de prompts via DB construída e abandonada.

**Forma B:** parcialmente em `knowledge_catalog` (DB) + ChromaDB (RAG) — mas isso é base científica, não conhecimento procedural sobre como o agente deve se comportar.

### 4.3 Cost management

| Item | Estado | Onde | Comentário |
|---|---|---|---|
| Cap por job | 🔴 ❌ | — | Sem teto. Loop em retries pode estourar. |
| Cap por tenant | ✅ | [billing_service.py:290](src/services/billing_service.py#L290) | `check_ai_allowance` antes; `record_ai_usage` depois. Bloqueia via `BillingLimitExceeded`. |
| Cap global | 🔴 ❌ | — | Sem `MAX_DAILY_SPEND_USD` ou similar. |
| Tracking por tenant | ✅ | `ai_audit_logs.clinic_id` + `record_ai_usage` | Granularidade boa. |
| Modelo barato p/ simples vs caro p/ crítico | 🟡 | gpt-4o-mini em tudo, Gemini 1.5 flash p/ RAG | Já é a estratégia barata. Sem rota pra modelo caro quando preciso. |
| Pricing table | 🔴 incompleto | [pricing.py](src/ai/pricing.py) | **Apenas gpt-4o-mini.** Quando o relatório científico usa Gemini (caminho normal), `calculate_cost()` retorna `0.0`. `ai_audit_logs.estimated_cost_usd` é silenciosamente subestimado. **Quanto mais o RAG funcionar, mais barato parece o sistema.** |
| Loop sem throttle | 🟡 | `cientifico._auto_ingest_evidence` | `time.sleep(0.4)` para PubMed (3 req/s); ChromaDB sem throttle mas é local. OK. |

### 4.4 Provider strategy

| Item | Estado | Comentário |
|---|---|---|
| Multi-provider | ✅ | OpenAI + Gemini |
| Failover automático | ✅ | OpenAI↔Gemini no triagem; Gemini→OpenAI no RAG |
| Roteamento por contexto | 🟡 parcial | RAG vai pro Gemini (contexto pode ser grande); demais vai pro OpenAI. Não há lógica explícita "se prompt > X tokens, use Y" |
| Vendor-lock | 🟡 | Sem abstração tipo `LLMProvider.complete()`; cada chain importa SDK diretamente. Mover para `litellm` ou wrapper próprio facilitaria. |

### 4.5 Evaluation strategy

🔴 **Não existe.** Evidências:
- `ls tests/ | grep -iE "eval|golden|baseline"` retornou vazio.
- Nenhum `audit_results.json` ou similar.
- Tests existentes ([test_cientifico_auto_ingest.py](tests/test_cientifico_auto_ingest.py), [test_agente_regulatorio.py](tests/test_agente_regulatorio.py), [test_admin_agents.py](tests/test_admin_agents.py)) são **mock-based** — testam fluxo de código, não qualidade da resposta do LLM.
- `quality_schema` migration 027 existe mas **PRECISA CONFIRMAÇÃO HUMANA** sobre se é eval harness ou sistema de qualidade clínica downstream.
- `document_review_workflows` (migration 034) é human-in-the-loop para relatórios regulatórios — não é eval automático.

**Consequência:** uma mudança em prompt que degrada extração de CID-10 em 20% só é detectável quando médico reclama. Sem sinal automático.

### 4.6 Failure modes conhecidos

Olhando `git log --since="2026-03-01" -- src/ai src/knowledge`:

| Commit | Tipo | Indica |
|---|---|---|
| `ed82aa7` C7 | feature | Agregação clínica via knowledge_catalog (anonimizada) |
| `b2019bc` C6 | feature | Auto-ingest PubMed em atendimento |
| `85d1f4a` P1 | feature | Base científica colaborativa com autoria |
| `d83c3f0` F3.4 | feature | Skill triage_adverse_event |
| `4a01f23` F1.6 | feature | Skill check_sandbox_eligibility |
| `c86508e` | feature gigante | "Backend completo + Arquitetura de Agentes IA + MemPalace + Google Files API" |

🟢 **Padrão observado:** commits em IA são quase todos `feat(ai/knowledge):`. Há **muito poucos `fix(ai):` ou `bug(ai):` recentes** — o que pode significar (a) sistema é estável, ou (b) bugs não estão sendo detectados/reportados (consistente com ausência de eval harness). Aposto em (b) parcialmente.

🔴 **Decisão MemPalace abandonada parcialmente:** memória do projeto registra `feedback_no_mempalace.md` (2026-04-24) — usuário classificou MemPalace como fraude e disse "não usar". Mas [src/ai/memory.py:66](src/ai/memory.py#L66) ainda faz `import mempalace` (lazy try/except) e [base.py](src/ai/agents/base.py) chama `diary_write`/`kg_add` em todo `agent.run()`. Em produção sem `mempalace` instalado, os calls retornam False/[] silenciosamente — fire-and-forget protege. Mas o **acoplamento de design** (palace_room por agente, hall de eventos, kg_add para fact-tracking) permanece. Tecnicamente seguro, semanticamente confuso.

---

## 5. Confronto com best practices

| Item | Estado | Evidência | Comentário |
|---|---|---|---|
| Toda chamada LLM passa por gateway com cost cap | ❌ | [chains.py:56-60](src/ai/chains.py#L56-L60) | OpenAI/Gemini clients instanciados módulo-level. Nenhum gateway intermediário. |
| Tools com descrições específicas e exemplos | ⚠️ | [schemas.py:108-180](src/ai/schemas.py#L108-L180) | `TRIAGE_TOOL_DEFINITION` é exemplar; demais (skills) não são tools formais. |
| Tools retornam erros que instruem o agente | ⚠️ | — | Como skills são chamadas Python, erro = exception. LLM nunca vê. |
| System prompt < 30 linhas (lean) | ❌ parcial | [prompts.py](src/ai/prompts.py) | Anamnese 30 ✅. Treatment 24 ✅. SciReport 20 ✅. **Triage 130** 🟡. **Prescriber 101** 🔴. |
| Skills carregadas sob demanda (Forma B) | ❌ | [prompts.py:5-130](src/ai/prompts.py#L5-L130) | Domain knowledge inline (Forma A). |
| Contexto compactado em conversas longas | ❌ | [chains.py:489](src/ai/chains.py#L489) | `prior_context` injetado cru. |
| Sub-agentes com contexto isolado | ⚠️ | [clinical_flow.py:34-104](src/ai/clinical_flow.py#L34-L104) | Cada agente roda standalone, mas chamadas são in-process e o prompt do próximo recebe o output do anterior. Não há sub-agent com janela própria. |
| Tool result clearing | ❌ | — | Não aplicável (não há multi-turn tool loops). |
| Output validado por schema (Pydantic) | ✅ | [chains.py:232-234](src/ai/chains.py#L232-L234) | Todas as etapas: `_run_and_validate` + Pydantic `ValidationError`. ✅ Forte. |
| Citation evaluator | ❌ | — | RAG cita references, mas nada checa que a cite existe no chunk. |
| Evaluation baseline + CI | ❌ | — | Sem golden set, sem CI gate. |
| Multi-tenant isolation no banco | ⚠️ | `clinic_id` em todas as tabelas IA | Sem RLS Postgres explícito (PRECISA CONFIRMAÇÃO HUMANA — ver auditoria de sistema). |
| Observability completa (request → tools → output rastreável) | ⚠️ | [service.py:168-189](src/ai/service.py#L168-L189) | `ai_audit_logs` rastreia. Mas: 3 colunas de timing (`clinical_time_ms`, `treatment_time_ms`, `report_time_ms`) **sempre ficam NULL** porque `SpecialistClinicalFlow.run()` retorna `token_usage` mas **não retorna `timings_ms`**. Service.py espera `result.get("timings_ms", {}).get("clinical")` que nunca existe. |
| Cost tracking por tenant | ⚠️ | `ai_audit_logs.estimated_cost_usd` | Existe, **mas zera quando o caminho é Gemini** (pricing.py incompleto). |
| Memory persistente bem definida | ⚠️ | [memory.py](src/ai/memory.py) | API limpa (diary/kg/search), mas backend (MemPalace) marcado como fraude pelo usuário e não está instalado. Memória "existe na interface, não no comportamento". |
| Provider abstraction (multi-LLM friendly) | ❌ | [chains.py](src/ai/chains.py) | Cada função sabe o SDK que usa. Adicionar Anthropic ou Mistral exige reescrever cada chain. |
| Guardrails de input | ✅ | [guardrails.py](src/ai/guardrails.py) | 3 camadas (regex+unicode+LLM opcional). 🔴 mas a 4ª (output) está definida e nunca chamada. |
| PII redaction antes de logar/persistir | ⚠️ | [memory.py:54-60](src/ai/memory.py#L54-L60) | Redaction implementada apenas para MemPalace. **`ai_audit_logs.input_payload` recebe payload bruto** ([service.py:174](src/ai/service.py#L174)). |

---

## 6. Top 5 problemas críticos

| # | Problema | Severidade | Esforço pra fixar | Por que importa |
|---|---|---|---|---|
| 1 | 🔴 `validate_output`/`sanitize_output` definidos em [guardrails.py:373,491](src/ai/guardrails.py#L373) e **nunca chamados** | Alta | Baixo (1-2h) | A Camada 4 dos guardrails (anti-exfiltração de credentials, anti-XSS no output) é dead code. Resposta do LLM vai pra paciente sem checagem. |
| 2 | 🔴 PII em `ai_audit_logs.input_payload`/`output_payload` sem redaction | Alta | Médio (1-2 dias) | LGPD: nome, idade, queixa, medicações, alergias, histórico, relato livre — tudo gravado em JSONB plain. `_sanitize_pii` existe em [memory.py:54](src/ai/memory.py#L54) mas só é usado pelo MemPalace path. |
| 3 | 🔴 `pricing.py` cobre só `gpt-4o-mini`; Gemini = $0 | Média | Baixo (2-4h) | Custo subnotificado sistematicamente quando RAG funciona (caminho normal). Decisões de billing/upgrade ficam erradas. |
| 4 | 🔴 `prompt_version="v1.0"` hardcoded em [service.py:45](src/ai/service.py#L45); `prompt_registry.py` e tabela `ai_prompt_versions` não plugados | Média | Médio (3-5 dias) | Não dá pra detectar drift de prompt; auditoria do hash é ilusória; rollback de prompt ruim exige deploy. |
| 5 | 🔴 Sem evaluation harness | Alta | Médio-alto (1-2 sprints) | Mudanças em prompt podem degradar 20% da extração CID-10 e ninguém percebe até médico reclamar. |

## 7. Top 5 ganhos rápidos

| # | Ganho | Esforço | Impacto |
|---|---|---|---|
| 1 | Plugar `validate_output(sanitized)` em [service.py:191](src/ai/service.py#L191) (antes do return) | 30 min | Fecha hole de XSS/exfiltração em 30 min. |
| 2 | Adicionar entry para `gemini-1.5-flash` no `MODEL_PRICING` ([pricing.py:3-8](src/ai/pricing.py#L3-L8)) e usar `report_model` do flow result | 1h | Cost tracking volta a refletir realidade. |
| 3 | Em `service.py:184-186`, popular `clinical_time_ms`/`treatment_time_ms`/`report_time_ms` retornando `timings_ms` no `SpecialistClinicalFlow.run()` (já tem `with measure(...)` mas o resultado é descartado) | 2-3h | 3 colunas do `ai_audit_logs` deixam de ser NULL — diagnóstico de gargalo por etapa. |
| 4 | Aplicar `_sanitize_pii` no `input_payload`/`output_payload` antes de `save_ai_audit_log` em [service.py:174,176](src/ai/service.py#L174-L176) | 2-3h | Fecha exposição LGPD imediatamente. Ainda preserva structure para debug — só redact identificadores. |
| 5 | Remover dead code MemPalace OU instalar dependência: decidir e executar uma das duas. Hoje é "Schrödinger's memory" | 1 dia (remoção) | Reduz superfície confusa do `BaseAgent`; remove dependência fantasma de [memory.py:66](src/ai/memory.py#L66). |

## 8. Top 3 oportunidades arquiteturais

### 8.1 Gateway central de LLM (`src/ai/llm_gateway.py`)

**Hoje:** [chains.py](src/ai/chains.py) instancia OpenAI e Gemini no módulo. `_run_openai`, `_run_gemini_with_retry`, `_run_triage_openai`, `_run_triage_gemini` duplicam lógica de retry+circuit_breaker+token-extraction.

**Proposta:** classe `LLMGateway` com `complete(prompt, schema, provider="openai", model="gpt-4o-mini", max_cost_usd=None)`. Centraliza:
- Pricing por modelo (resolve problema #3 acima).
- Cost cap por job (resolve problema crítico #6 implícito).
- Logging estruturado por chamada.
- Provider failover.
- Tokens + custo retornados sempre.

**Esforço:** 1-2 sprints. Mudança grande mas bem delimitada — chains.py reescrito em torno do gateway, agentes não mudam.

### 8.2 Evaluation harness contínuo

**Hoje:** zero golden tests. Mudança em prompt = roleta russa.

**Proposta:**
- `tests/eval/cases/` com 30-50 JSONs: input clínico + expected (não literal — checks como "deve extrair `dor lombar` ou variante", "treatment_plan deve ter cannabinoid_ratio em formato `X:Y`", "scientific_report deve citar pelo menos 1 reference se rag_used=true").
- `tests/eval/runner.py`: roda flow contra LLM real (apenas em CI gated, não em PR comum por custo) e gera diff vs baseline.
- `tests/eval/baseline.json`: snapshot atualizado manualmente quando dev confirma que mudança é intencional.
- CI step opcional via label `[run-evals]` em PR.

**Esforço:** 1 sprint para infra + 1 sprint para curar 30 casos.

### 8.3 Skills como Forma B (loadable knowledge)

**Hoje:** `PRESCRIBER_SYSTEM_PROMPT` e `TRIAGE_AGENT_SYSTEM_PROMPT` carregam tabelas inteiras (11 condições terapêuticas, 10 widgets, 5 interações).

**Proposta:**
- `src/ai/skills/dosage_protocols.json` — tabela de protocolos por condição.
- `src/ai/skills/widget_catalog.json` — catálogo de widgets com schemas.
- `src/ai/skills/cyp450_interactions.json` — matriz de interações.
- `prompt_registry` carrega skill JSON sob demanda, formata pequena seção do prompt.
- Editar protocolo de fibromialgia = mudar 1 linha em JSON, não scroll por 100 linhas de prompt.

**Esforço:** 1-2 sprints. Junta bem com 8.1 (registry virou load point).

---

## 9. Aderência aos targets declarados pelo solicitante

Memory project diz: **app paciente é a próxima sprint depois do C6/C7 ter shipado**. Auditoria de sistema está rolando em paralelo. Não há menção a apresentação para investidor/evento crítico iminente, então uso "fechamento de fase" como target.

**Para fechar fase de IA com confiança:**
- 🔴 **Não está pronto** se "fechar fase" significa "agora roda em escala em produção sem alguém olhando".
- 🟡 **Está pronto** se significa "MVP funcional para clínicas piloto, com supervisão médica downstream".

**Bloqueadores reais para "deploy and forget":**
1. PII no audit log (LGPD).
2. Cost tracking incompleto (cobrança correta de tenants).
3. Sem regressão em CI (qualquer mudança em prompt vira roleta).

Os outros itens são tech debt aceitável para versão 1.x.

---

## 10. Perguntas em aberto

1. 🟡 **Triagem entra no `ai_audit_logs`?** O agente é chamado de webhook WhatsApp / chat web, não pelo `CannabIAService.process_patient_case`. PRECISA CONFIRMAÇÃO se há outro path de logging para triagem. Se não, ~50% das chamadas LLM (estimativa) ficam fora do audit.

2. 🟡 **Prescritor está no flow real?** Ele tem rules engine + safety clamp + CYP450, mas `SpecialistClinicalFlow` usa `AgenteTratamento` (que não tem essa proteção). Decisão arquitetural ou bug?

3. 🟡 **MemPalace decisão final?** Código importa, feedback memory diz "fraude, não usar". Manter dead-code via fire-and-forget é OK, mas confunde. Decidir e documentar.

4. 🟡 **`ai_prompt_versions` table tem dados?** Schema existe. PRECISA CONFIRMAÇÃO se há rows. Se sim, por que `service.py` não consulta? Se não, por que a tabela?

5. 🟡 **`knowledge_catalog` é global ou por tenant?** Schema [migration 016] precisa ser checado. Se global, todos os tenants compartilham descobertas — bom para rede, possível issue para clínicas que querem isolar IP intelectual.

6. 🟢 **Existe RLS no Postgres?** Reportar a auditoria de sistema. Não verifiquei em detalhe.

7. 🟡 **`triage_intake_service` (referenciado em [tests/test_triage_intake_service.py](tests/test_triage_intake_service.py)) é o ponto de entrada produtivo?** Não foi auditado neste deep dive.

---

## 11. Recomendação de prioridades (30/60/90 dias)

### 30 dias — Bloqueadores e fixes triviais

1. **Plugar Camada 4 de guardrails** ([service.py:191](src/ai/service.py#L191)) — 30 min, fecha hole de output.
2. **Corrigir pricing para Gemini** ([pricing.py](src/ai/pricing.py)) — 1h, métrica de custo volta.
3. **Sanitizar PII antes de gravar `input_payload`/`output_payload`** ([service.py:174,176](src/ai/service.py#L174)) — 1 dia, fecha LGPD risk.
4. **Popular `timings_ms` no flow** ([clinical_flow.py:34-104](src/ai/clinical_flow.py#L34-L104) precisa retornar dict) — 3h, observabilidade por etapa volta.
5. **Decidir MemPalace** — manter ou remover, documentar a decisão.
6. **Confirmar logging de triagem** — pergunta em aberto #1 deste relatório precisa virar PR.

### 60 dias — Ganhos rápidos + 1 transformacional

1. **Plugar `prompt_registry` em `service.py`** — 3-5 dias. Resolve drift de prompt.
2. **Mudar prompts grandes (Triage, Prescriber) para Forma B** — 1 sprint. Catálogos viram JSON loadable.
3. **Implementar `LLMGateway` central** — 1-2 sprints. Resolve cost cap, multi-provider, observabilidade unificada.

### 90 dias — Outras oportunidades

1. **Evaluation harness com 30-50 casos clínicos + CI gated** — 2 sprints. Defesa contra regressão silenciosa.
2. **Citation evaluator no relatório científico** — verifica que `references` realmente apareceu nos chunks RAG. 1 sprint.
3. **Provider abstraction** — adicionar suporte a Anthropic e/ou litellm para evitar vendor-lock. Já preparado pelo gateway. 1 sprint.

---

**Fim do relatório.**
