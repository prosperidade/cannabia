# 21 — Arquitetura de Agentes IA da Cannab'IA

## Visao Geral

```
                           +---------------------+
                           |    Orchestrator      |
                           |  (ChainStep runner)  |
                           +----------+----------+
                                      |
              +-----------+-----------+-----------+-----------+-----------+
              |           |           |           |           |           |
        +-----v----+ +---v------+ +--v-------+ +-v--------+ +v--------+ +v---------+
        | Triagem  | | Anamnese | | Prescritor| |Cientifico| |Regulat. | | FollowUp |
        +-----+----+ +---+------+ +--+-------+ +-+--------+ ++--------+ ++---------+
              |           |           |           |           |           |
              +-----+-----+-----+-----+-----+----+-----+-----+-----+----+
                    |                 |                  |                |
              +-----v-----+    +-----v------+    +------v------+  +-----v-----+
              | MemPalace  |    | ChromaDB   |    | Google Files|  | PostgreSQL|
              | (memoria)  |    | (artigos)  |    | (legislacao)|  | (catalogo)|
              +------------+    +------------+    +-------------+  +-----------+

        +-----------------------------------------------------------------------------+
        |                        AgenteExtrator                                       |
        |   PubMed search | classify | ingest (ChromaDB/Google Files) | monitors      |
        +-----------------------------------------------------------------------------+
```

Todos os agentes herdam de `BaseAgent` e compartilham:
- Registro de skills (funcoes invocaveis por nome)
- Memoria persistente via MemPalace (fire-and-forget)
- Auto-logging de execucao (diary entries)
- Metricas padronizadas (`AgentResult`)

**Arquivos-chave:**
- `src/ai/agents/__init__.py` — exports publicos
- `src/ai/agents/base.py` — classe base, Skill, AgentResult
- `src/ai/agents/orchestrator.py` — encadeamento de agentes
- `src/ai/memory.py` — integracao MemPalace
- `src/knowledge/google_files.py` — Google Files API
- `mempalace.yaml` — configuracao dos rooms

---

## BaseAgent — Classe Base

**Arquivo:** `src/ai/agents/base.py`

Classe abstrata que toda agent herda. Define o contrato para execucao, skills e memoria.

### Atributos da Classe

| Atributo | Tipo | Descricao |
|---|---|---|
| `palace_room` | `str` | Room no MemPalace para diary/search deste agente |
| `agent_name` | `str` | Nome de exibicao (usado em logs e ChainResult) |
| `description` | `str` | Descricao do que o agente faz |

### AgentResult

Resultado padrao de qualquer execucao de agente.

```python
@dataclass
class AgentResult:
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens: Dict[str, int] = field(default_factory=dict)     # {"input_tokens", "output_tokens", "total_tokens"}
    duration_ms: int = 0
    confidence: float = 0.0
    agent_name: str = ""
    skills_used: List[str] = field(default_factory=list)
```

### Skill

Funcao registrada que um agente pode invocar.

```python
@dataclass
class Skill:
    name: str
    description: str
    handler: Callable
    input_schema: Optional[Dict] = None
    output_schema: Optional[Dict] = None
```

### Metodos Principais

| Metodo | Descricao |
|---|---|
| `register_skill(name, handler, description, ...)` | Registra uma skill no agente |
| `invoke_skill(name, **kwargs)` | Invoca skill por nome |
| `recall_memory(query, diary_n=5, search_n=3)` | Busca contexto no MemPalace |
| `remember(content)` | Salva nota no diary (PII sanitizada) |
| `remember_fact(subject, predicate, obj, confidence)` | Adiciona fato ao knowledge graph |
| `get_diary(last_n=10)` | Le entradas recentes do diary |
| `execute(**kwargs) -> AgentResult` | **Abstrato** — logica principal do agente |
| `run(**kwargs) -> AgentResult` | Wrapper com timing, auto-logging e error handling |

### Principio Fire-and-Forget

Todas as operacoes de memoria sao envolvidas em `try/except`. Se o MemPalace nao estiver instalado ou falhar, o agente **continua executando normalmente**. Memoria nunca bloqueia execucao clinica.

### Fluxo do metodo `run()`

1. Extrai `_memory_query` dos kwargs (se presente)
2. Faz `recall_memory()` e injeta como `_memory_context`
3. Chama `execute()` (implementado por cada agente)
4. Loga `[OK]` ou `[FAIL]` no diary automaticamente
5. Se `result.data["_kg_subject"]` existe, adiciona fato ao knowledge graph
6. Retorna `AgentResult` com `duration_ms` preenchido

---

## Orchestrator

**Arquivo:** `src/ai/agents/orchestrator.py`

Encadeia multiplos agentes em sequencia, passando dados entre eles.

### ChainStep

```python
@dataclass
class ChainStep:
    agent_class: Type[BaseAgent]          # Classe do agente a executar
    input_map: Optional[Dict[str, str]]   # Mapeia output anterior -> input deste step
    required: bool = True                 # Se False, chain continua mesmo se falhar
    memory_query: Optional[str] = None    # Query para recall de memoria
```

### ChainResult

```python
@dataclass
class ChainResult:
    success: bool
    steps: List[AgentResult]
    final_data: Dict[str, Any]
    total_duration_ms: int = 0
    total_tokens: Dict[str, int] = field(default_factory=dict)
    chain_name: str = ""
    failed_at: Optional[str] = None
```

### Como funciona o data passing

O Orchestrator mantém um dicionario `accumulated` que começa com `initial_data` e recebe `result.data` de cada step que sucede. O `input_map` resolve caminhos com ponto:

```python
# input_map={"treatment_plan": "data.treatment_plan"}
# Navega: accumulated["data"]["treatment_plan"]
```

Se `input_map` e `None`, o step recebe todo o `accumulated` como kwargs.

### Cache de Agentes

O Orchestrator mantem um `_agent_cache` interno. Cada classe de agente e instanciada apenas uma vez.

### Logging de Chains

- **Sucesso:** `diary_write("pipeline_anamnese", "[CHAIN OK] {name} agents=[...] duration={ms}ms")`
- **Falha:** `diary_write("pipeline_anamnese", "[CHAIN FAIL] {name} failed_at={agent} step={i}/{n}")`
- **Knowledge Graph:** Se `clinic_id` fornecido, registra `clinic_{id} -> chain_{name}_completed`

### Exemplo de Uso

```python
orch = Orchestrator()
result = orch.run_chain(
    name="diagnostico_completo",
    steps=[
        ChainStep(AgenteAnamnese),
        ChainStep(AgentePrescritor, input_map={"clinical_analysis": "data.clinical_analysis"}),
        ChainStep(AgenteCientifico, input_map={"treatment_plan": "data.treatment_plan"}),
    ],
    initial_data={"patient_data": {...}},
)
```

---

## Agentes Clinicos

### 1. AgenteTriagem

**Arquivo:** `src/ai/agents/triagem.py`

| Propriedade | Valor |
|---|---|
| **Room** | `pipeline_anamnese` |
| **agent_name** | `triagem` |
| **Descricao** | Extrai condicoes clinicas do relato do paciente usando widgets interativos |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `extract_conditions` | Extrai condicoes clinicas do texto do paciente | `patient_message: str`, `patient_name`, `age`, `clinic_id`, `prior_context`, `provider` | `{"triage_response": dict, "tokens": dict}` |
| `detect_red_flags` | Detecta sinais de alerta (dor toracica, ideacao suicida, etc) | `triage_response: dict` | `{"red_flags": list, "has_red_flags": bool}` |

**LLMs usados:** OpenAI ou Gemini (configuravel via `provider` param)

**Dependencias:** `src.ai.chains.run_triage_agent()`

**Fluxo de execucao:**
1. Invoca `extract_conditions` com a mensagem do paciente
2. Invoca `detect_red_flags` sobre o resultado
3. Registra cada condicao no knowledge graph: `{condition} -> detected_in_triage -> confidence={x}`
4. Confidence: 0.85 (sem red flags) ou 0.95 (com red flags — urgencia)

**Keywords de alta urgencia:** `suicid`, `toraci`, `infart`, `convuls`, `anafilax`

---

### 2. AgenteAnamnese

**Arquivo:** `src/ai/agents/anamnese.py`

| Propriedade | Valor |
|---|---|
| **Room** | `pipeline_anamnese` |
| **agent_name** | `anamnese` |
| **Descricao** | Analisa sintomas e gera avaliacao clinica estruturada |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `analyze_symptoms` | Gera analise clinica a partir dos dados do paciente | `**patient_data` | `{"clinical_analysis": dict, "tokens": dict}` |
| `assess_risk_level` | Avalia nivel de risco do paciente | `clinical_analysis: dict` | `{"risk_level": str, "red_flags": list, "is_high_risk": bool}` |

**LLMs usados:** Via `src.ai.chains.run_clinical_analysis()` (OpenAI/Gemini)

**Dependencias:** `src.ai.chains.run_clinical_analysis()`

**Fluxo de execucao:**
1. Aceita `patient_data` dict ou campos individuais
2. Se `_memory_context` presente, injeta `_similar_cases` do recall
3. Invoca `analyze_symptoms`
4. Invoca `assess_risk_level`
5. Confidence: 0.8 (sem high risk) ou 0.9 (com high risk)

**Risk levels:** `alto`, `critico` (high risk), `medio`, `baixo`

---

### 3. AgentePrescritor

**Arquivo:** `src/ai/agents/prescritor.py`

| Propriedade | Valor |
|---|---|
| **Room** | `pipeline_prescricao` |
| **agent_name** | `prescritor` |
| **Descricao** | Calcula dosagem CBD/THC com rules engine, LLM e safety clamp |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `calculate_safety_limits` | Calcula limites de seguranca deterministicos (rules engine) | `**dosage_input` (campos de `DosageInput`) | `{"safety_limits": dict}` |
| `calculate_dosage` | Gera recomendacao de dosagem completa (rules + LLM + clamp) | `**dosage_input` | `{"recommendation": dict, "safety_limits": dict, "tokens": dict}` |
| `check_interactions` | Verifica interacoes medicamentosas CYP450 | `medications: list` | `{"interactions": list, "has_interactions": bool, "dose_multiplier": float}` |

**LLMs usados:** Via `src.ai.prescriber.run_prescriber()` (OpenAI GPT-4)

**Dependencias:**
- `src.ai.prescriber.run_prescriber()`
- `src.ai.prescriber.calculate_safety_limits()`
- `src.ai.prescriber._detect_drug_interactions()`
- `src.ai.schemas.DosageInput`

**Arquitetura de 3 camadas:**

1. **Rules Engine** (`calculate_safety_limits`): Calculo deterministico de limites maximos de mg/dia, ratio CBD:THC, e fase de titulacao. Nao usa LLM.
2. **LLM** (`calculate_dosage` via `run_prescriber`): Gera recomendacao personalizada considerando historico e condicao do paciente.
3. **Safety Clamp**: O `run_prescriber` aplica um clamp final — a dosagem LLM nunca excede os limites do rules engine.

**Knowledge Graph:** Registra `{cannabinoid_ratio} -> prescribed_for -> {main_complaint}` apos cada prescricao.

**Interacoes CYP450:** O skill `check_interactions` retorna um `dose_multiplier` que pode reduzir a dosagem recomendada.

---

### 4. AgenteCientifico

**Arquivo:** `src/ai/agents/cientifico.py`

| Propriedade | Valor |
|---|---|
| **Room** | `pipeline_cientifico` |
| **agent_name** | `cientifico` |
| **Descricao** | Gera relatorio cientifico com evidencias de PubMed/Cochrane via RAG |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `search_evidence` | Busca evidencias cientificas no ChromaDB | `query_text: str`, `n_results: int = 5` | `{"chunks": list, "has_evidence": bool}` |
| `generate_report` | Gera relatorio cientifico com ou sem RAG | `treatment_plan: dict`, `chunks: list = None` | `{"report": dict, "tokens": dict, "model": str, "rag_used": bool}` |

**LLMs usados:**
- **Com RAG (chunks disponiveis):** `gemini-1.5-flash` via `run_scientific_report_rag()`
- **Sem RAG (fallback):** `gpt-4o-mini` via `run_scientific_report()`

**Dependencias:**
- `src.knowledge.embeddings.EmbeddingClient`
- `src.knowledge.vector_store.KnowledgeStore`
- `src.ai.chains.run_scientific_report_rag()`
- `src.ai.chains.run_scientific_report()`
- `src.ai.schemas.TreatmentPlan`

**Fluxo de execucao:**
1. Serializa `treatment_plan` como JSON para query de busca
2. Invoca `search_evidence` no ChromaDB
3. Invoca `generate_report` — usa RAG se chunks disponiveis, senao fallback
4. Confidence: 0.85 (com RAG) ou 0.70 (sem RAG)
5. Retorna `chunks_used`, `rag_used`, `model` nos dados

---

### 5. AgenteRegulatorio

**Arquivo:** `src/ai/agents/regulatorio.py`

| Propriedade | Valor |
|---|---|
| **Room** | `regulatorio_anvisa` |
| **agent_name** | `regulatorio` |
| **Descricao** | Verifica compliance regulatoria ANVISA/CFM via Google Files API |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `check_anvisa_compliance` | Verifica se prescricao atende RDC 327/2019 e normas ANVISA | `prescription: dict` | `{"compliant": bool, "issues": list, "checked_norms": list}` |
| `query_legislation` | Consulta legislacao com contexto completo via Google Files API | `question: str`, `file_names: list = None` | `{"result": dict, "usage": dict, "source": str}` |

**LLMs usados:** Gemini (`gemini-2.0-flash`) via Google Files API para analise de legislacao

**Dependencias:**
- `src.knowledge.google_files.query_legislation_structured()`

**Regras deterministicas de compliance (sem LLM):**
- THC > 40mg/dia: requer justificativa especial (RDC 327 Art. 8)
- Via inalatoria: nao regulamentada pela ANVISA
- Normas verificadas: `RDC 327/2019`, `RDC 660/2022`

**Fluxo de execucao:**
1. Se `prescription` presente, verifica compliance ANVISA
2. Se `question` presente, consulta legislacao via Google Files API
3. Se compliance falha, loga issues no diary
4. Confidence: 0.9 (compliant) ou 0.6 (non-compliant)

---

### 6. AgenteFollowUp

**Arquivo:** `src/ai/agents/follow_up.py`

| Propriedade | Valor |
|---|---|
| **Room** | `crm_telemetria` |
| **agent_name** | `follow_up` |
| **Descricao** | Gerencia retornos, analisa diario de sintomas e sugere ajustes de dosagem |

**Skills:**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `analyze_diary` | Analisa entradas do diario de sintomas do paciente | `diary_entries: list` | `{"trend": str, "avg_scores": dict, "improving": bool\|None, "entries_analyzed": int}` |
| `suggest_adjustment` | Sugere ajuste de dosagem baseado na evolucao | `diary_analysis: dict`, `current_dosage: dict` | `{"action": str, "reason": str, "confidence": float}` |
| `schedule_return` | Determina data de retorno baseado no protocolo | `treatment_phase: str` | `{"return_in_days": int, "phase": str}` |

**LLMs usados:** Nenhum — toda logica e deterministica

**Logica de analise de trend:**
- Divide entries em duas metades
- Compara media da primeira metade vs segunda metade
- `improving`: segunda metade > primeira metade
- `stable_or_worsening`: caso contrario

**Logica de ajuste:**

| Trend | Score Overall | Acao | Confidence |
|---|---|---|---|
| `improving` | >= 7 | `maintain` | 0.85 |
| `improving` | < 7 | `increase` (START LOW GO SLOW) | 0.70 |
| `stable_or_worsening` | pain > 5 | `increase` + reavaliar ratio | 0.75 |
| `stable_or_worsening` | >= 7 | `maintain` | 0.80 |
| `insufficient_data` | — | `maintain` | 0.50 |

**Protocolo de retorno:**

| Fase | Dias para retorno |
|---|---|
| `inicial` | 7 |
| `titulacao` | 14 |
| `ajuste` | 14 |
| `manutencao` | 30 |

---

### 7. AgenteExtrator

**Arquivo:** `src/ai/agents/extrator.py`

| Propriedade | Valor |
|---|---|
| **Room** | `pipeline_cientifico` |
| **agent_name** | `extrator` |
| **Descricao** | Busca, classifica e ingere documentos na base de conhecimento (PubMed, ANVISA, Scholar) |

**Skills (10 no total):**

| Skill | Descricao | Input | Output |
|---|---|---|---|
| `search_pubmed` | Busca artigos no PubMed por termo | `query: str`, `max_results: int = 10` | `{"articles": list, "total_found": int, "query": str}` |
| `fetch_pubmed_article` | Busca abstract completo por PMID | `pmid: str` | `{"pmid": str, "abstract": str, "success": bool}` |
| `search_legislation` | Busca legislacao em fontes oficiais | `query: str` | `{"results": list, "query": str}` |
| `classify_document` | Classifica documento por tipo e storage | `title: str`, `content: str`, `filename: str` | `{"doc_type": str, "storage_type": str, "reason": str, ...}` |
| `ingest_to_chromadb` | Ingere documento como chunks no ChromaDB | `text: str`, `metadata: dict`, `chunk_size: int = 1000` | `{"chunks_total": int, "chunks_stored": int, "success": bool}` |
| `ingest_to_google_files` | Envia documento para Google Files API | `filepath: str`, `display_name: str` | `{"uri": str, "name": str, "success": bool}` |
| `register_in_catalog` | Registra no catalogo unificado (PostgreSQL) | `doc_data: dict` | `{"registered": bool, "catalog_id": int}` ou `{"registered": false, "reason": str}` |
| `auto_search_and_ingest` | Busca automatica e ingesta resultados | `terms: list`, `max_per_term: int = 5` | `{"terms_searched": int, "total_found": int, "total_registered": int, "details": list}` |
| `check_monitor` | Verifica uma fonte monitorada por novidades | `monitor: dict` | `{"checked": bool, "new_items": list, "items_count": int, "hash": str, "changed": bool}` |
| `run_all_monitors` | Executa todos os monitores ativos no horario | `(nenhum)` | `{"monitors_checked": int, "total_new_items": int, "results": list}` |

**LLMs usados:** Nenhum diretamente — usa PubMed E-utilities (REST API publica) e Google Files API

**Acoes do `execute()`:**

| Action | Skills invocados |
|---|---|
| `auto_search` (default) | `search_pubmed`, `fetch_pubmed_article`, `classify_document`, `register_in_catalog`, `search_legislation` |
| `classify` | `classify_document` |
| `ingest_file` | `classify_document` + `ingest_to_google_files` ou `ingest_to_chromadb` |
| `search_pubmed` | `search_pubmed` |
| `search_legislation` | `search_legislation` |
| `run_monitors` | `run_all_monitors`, `check_monitor` |

**Termos de busca padrao (`DEFAULT_CANNABIS_TERMS`):**
- `cannabidiol therapeutic`
- `CBD chronic pain systematic review`
- `THC epilepsy clinical trial`
- `cannabis medicinal anxiety`
- `cannabinoid dosage safety`
- `CBD sleep disorder`
- `medical cannabis pharmacokinetics`

**URLs de legislacao conhecidas:**
- `RDC 327/2019` — ANVISA
- `RDC 660/2022` — ANVISA
- `Lei 11.343/2006` — Planalto

**Classificacao de documentos (regex-based):**

| Tipo | Patterns | Storage |
|---|---|---|
| `legislation` | `rdc\s*\d+`, `resolucao`, `portaria`, `lei\s*\d+`, `decreto`, `anvisa`, `cfm`, etc | `google_files` |
| `article` | `abstract`, `doi:`, `pubmed`, `clinical\s*trial`, `systematic\s*review`, `randomized`, etc | `chromadb` |
| `guideline` | `guideline`, `protocolo`, `consenso`, `diretriz`, `manual de/do/da` | `google_files` |
| `unknown` | nenhum match | `chromadb` (default) |

**Rate limiting:** 0.4s entre requests ao PubMed (E-utilities pede max 3 req/s).

**Deduplicacao:** Verifica DOI e URL antes de registrar no catalogo.

---

## MemPalace — Memoria Persistente

**Arquivo:** `src/ai/memory.py`  
**Config:** `mempalace.yaml`

### Wing e Rooms

**Wing:** `cannabia_clinical`

| Room | Descricao | Usada por |
|---|---|---|
| `pipeline_anamnese` | Padroes de anamnese, sintomas recorrentes, perfis de paciente | AgenteTriagem, AgenteAnamnese, Orchestrator (chain logs) |
| `pipeline_prescricao` | Dosagens, ratios CBD/THC, titulacoes, outcomes acumulados | AgentePrescritor |
| `pipeline_cientifico` | Evidencias consultadas, artigos mais citados, lacunas identificadas | AgenteCientifico, AgenteExtrator |
| `regulatorio_anvisa` | RDCs, resolucoes, atualizacoes normativas aplicadas | AgenteRegulatorio |
| `regulatorio_cfm` | Normas do CFM sobre prescricao de canabinoides | (disponivel, nao atribuida) |
| `whatsapp_flow` | Padroes de conversa, taxa de conclusao de anamnese, abandono | (disponivel) |
| `crm_telemetria` | Follow-up patterns, IoT readings, diary correlations | AgenteFollowUp |
| `multi_tenant` | Padroes anonimizados entre clinicas (dosagem media, condicoes top) | (disponivel) |
| `backend` | Flask routes, migrations, infra decisions | (dev) |
| `frontend` | Next.js pages, components, design system | (dev) |

### Funcoes Disponiveis

| Funcao | Descricao |
|---|---|
| `diary_write(room, content, hall="hall_events")` | Escreve entrada no diary do agente |
| `diary_read(room, last_n=10)` | Le entradas recentes do diary |
| `kg_add(subject, predicate, obj, confidence="high")` | Adiciona fato ao knowledge graph |
| `kg_query(entity, limit=10)` | Consulta fatos sobre uma entidade |
| `search(query, room=None, limit=5)` | Busca semantica no palace |
| `save_to_room(room, content, hall="hall_facts")` | Salva conteudo em room/hall especifico |
| `recall_agent_context(room, query, diary_n=5, search_n=3)` | Recall completo: diary + search |
| `_sanitize_pii(text)` | Remove PII antes de salvar (LGPD) |

### Compressao AAAK

O MemPalace usa compressao AAAK (Agents Ask, Agents Know) — entradas sao comprimidas semanticamente para reduzir tokens. Startup tokens estimados: **170 tokens** por agent recall.

### LGPD Compliance

**Patterns removidos antes de salvar no MemPalace:**

| Tipo | Pattern | Substituicao |
|---|---|---|
| CPF | `\d{3}\.\d{3}\.\d{3}-\d{2}` | `[CPF_REDACTED]` |
| CNPJ | `\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}` | `[CNPJ_REDACTED]` |
| Telefone (sufixo) | `\d{4,5}-?\d{4}` | `[PHONE_REDACTED]` |
| Telefone (BR completo) | `55\d{10,11}` | `[PHONE_REDACTED]` |
| Email | `[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+` | `[EMAIL_REDACTED]` |
| Endereco | `(Rua\|Av\|Avenida\|Alameda\|Travessa) + nome + numero` | `[ADDRESS_REDACTED]` |
| Nome de paciente | `paciente/patient/nome: NomeSobrenome` | `[PATIENT_NAME_REDACTED]` |

---

## Knowledge Base — Arquitetura Hibrida

O sistema usa **tres backends** de conhecimento, cada um otimizado para um tipo de documento:

### ChromaDB — Artigos Cientificos

- **Uso:** Artigos do PubMed, reviews, clinical trials
- **Formato:** Chunks de ~1000 caracteres com embeddings vetoriais
- **Busca:** Semantica (query -> embedding -> nearest neighbors)
- **Motivo:** Artigos sao autocontidos por secao — chunks funcionam bem
- **Classes:** `EmbeddingClient`, `KnowledgeStore`

### Google Files API — Legislacao

- **Uso:** RDCs ANVISA, resolucoes CFM, Lei de Drogas
- **Formato:** Documento completo (PDF/TXT) enviado via Files API
- **Busca:** Gemini 2.0 Flash analisa o documento inteiro com system instruction especializada
- **Motivo:** Leis referenciam outros artigos internamente — chunks quebram referencias cruzadas
- **Acuracia:** ~95% com contexto completo vs ~70% com chunks
- **Cache:** In-memory + `data/file_catalog.json` para persistencia entre restarts
- **Checksum:** SHA-256 — re-upload apenas quando arquivo muda
- **Model:** `gemini-2.0-flash` (configuravel via `GEMINI_FILES_MODEL`)

### PostgreSQL `knowledge_catalog` — Catalogo Unificado

Registro central de TODOS os documentos independente de onde estao armazenados.

### Arvore de Decisao de Roteamento

```
Documento recebido
    |
    +-- Regex match legislacao? --> Google Files API
    |       (rdc, resolucao, portaria, lei, decreto, anvisa, cfm, etc)
    |
    +-- Regex match artigo cientifico? --> ChromaDB (chunks)
    |       (abstract, doi, pubmed, clinical trial, systematic review, etc)
    |
    +-- Regex match guideline? --> Google Files API
    |       (guideline, protocolo, consenso, diretriz, manual)
    |
    +-- Nenhum match --> ChromaDB (default)
```

### Web Monitoring (`knowledge_monitors`)

O AgenteExtrator verifica fontes cadastradas periodicamente:
- **PubMed queries:** Busca novos artigos por termos de pesquisa
- **HTML pages:** Detecta mudancas por hash de conteudo
- **Intervalo:** Configuravel por monitor (24h, 48h, 72h, 168h)
- **Deteccao de mudanca:** SHA-256 hash do conteudo/PMIDs

---

## Chains Pre-definidas

### Chain: Diagnostico Completo

```
Triagem -> Anamnese -> Prescritor -> Cientifico -> Regulatorio
```

| Step | Agente | input_map | required |
|---|---|---|---|
| 1 | AgenteTriagem | (initial_data) | true |
| 2 | AgenteAnamnese | `triage_response` do step anterior | true |
| 3 | AgentePrescritor | `clinical_analysis` da anamnese | true |
| 4 | AgenteCientifico | `treatment_plan` do prescritor | true |
| 5 | AgenteRegulatorio | `recommendation` do prescritor | false |

Pipeline completo: recebe mensagem do paciente, extrai condicoes, analisa clinicamente, calcula dosagem, gera relatorio cientifico e verifica compliance.

### Chain: Prescricao Segura

```
Anamnese -> Prescritor -> Regulatorio
```

| Step | Agente | input_map | required |
|---|---|---|---|
| 1 | AgenteAnamnese | (patient_data) | true |
| 2 | AgentePrescritor | `clinical_analysis` | true |
| 3 | AgenteRegulatorio | `recommendation` | true |

Pipeline focado: pula triagem e relatorio cientifico. Util quando condicoes ja foram identificadas.

### Chain: Follow-up Inteligente

```
FollowUp -> (se adjustment=increase) -> Prescritor
```

| Step | Agente | input_map | required |
|---|---|---|---|
| 1 | AgenteFollowUp | `diary_entries`, `current_dosage`, `treatment_phase` | true |
| 2 | AgentePrescritor (condicional) | `adjustment_suggestion` | false |

O segundo step so e invocado se `adjustment_suggestion.action == "increase"`.

### Chain: Ingestao de Conhecimento

```
Extrator (auto_search) -> classify -> route (ChromaDB ou Google Files)
```

| Step | Acao | Descricao |
|---|---|---|
| 1 | `search_pubmed` | Busca artigos por termos |
| 2 | `fetch_pubmed_article` | Busca abstract de cada artigo |
| 3 | `classify_document` | Determina tipo e storage |
| 4 | `register_in_catalog` | Registra no PostgreSQL |
| 5 | (futuro) | Ingestao no ChromaDB ou Google Files |

---

## Tabelas do Banco de Dados

### knowledge_catalog

**Migration:** `016_knowledge_catalog.sql`

| Campo | Tipo | Descricao |
|---|---|---|
| `id` | `SERIAL PK` | ID unico |
| `clinic_id` | `INT` | Tenant (default 1) |
| `title` | `VARCHAR(500)` | Titulo do documento |
| `doc_type` | `VARCHAR(50)` | `article`, `legislation`, `guideline`, `protocol`, `bula` |
| `source` | `VARCHAR(50)` | `pubmed`, `scholar`, `anvisa`, `planalto`, `cfm`, `manual_upload`, `crossref` |
| `source_url` | `TEXT` | URL de origem |
| `doi` | `VARCHAR(100)` | Digital Object Identifier |
| `category` | `VARCHAR(100)` | `cannabis_medicinal`, `epilepsia`, `dor_cronica`, etc |
| `subcategory` | `VARCHAR(100)` | Subcategoria |
| `tags` | `JSONB` | Tags em array JSON |
| `authors` | `JSONB` | Lista de autores |
| `journal` | `VARCHAR(255)` | Nome do periodico |
| `published_date` | `DATE` | Data de publicacao |
| `language` | `VARCHAR(10)` | Idioma (default `pt-BR`) |
| `abstract` | `TEXT` | Resumo/abstract |
| `norm_number` | `VARCHAR(100)` | Numero da norma (ex: `RDC 327/2019`) |
| `norm_body` | `VARCHAR(100)` | Orgao emissor (`ANVISA`, `CFM`) |
| `norm_status` | `VARCHAR(50)` | `vigente`, `revogada`, `alterada` |
| `storage_type` | `VARCHAR(50)` | `chromadb`, `google_files`, `both`, `pending` |
| `chromadb_chunks` | `INT` | Numero de chunks no ChromaDB |
| `google_file_uri` | `TEXT` | URI no Google Files API |
| `google_file_name` | `VARCHAR(255)` | Nome no Google Files API |
| `local_path` | `TEXT` | Caminho local do arquivo |
| `file_hash` | `VARCHAR(64)` | SHA-256 do arquivo original |
| `file_size_bytes` | `INT` | Tamanho em bytes |
| `mime_type` | `VARCHAR(100)` | MIME type (default `application/pdf`) |
| `status` | `VARCHAR(50)` | `pending`, `downloading`, `processing`, `indexed`, `failed`, `archived` |
| `error_message` | `TEXT` | Mensagem de erro (se falhou) |
| `ingested_by` | `VARCHAR(100)` | `agent_extrator`, `manual_upload`, `auto_search`, `monitor_auto` |
| `ingested_at` | `TIMESTAMPTZ` | Timestamp de ingestao |

**Indices:**
- `idx_knowledge_catalog_type` (doc_type)
- `idx_knowledge_catalog_source` (source)
- `idx_knowledge_catalog_status` (status)
- `idx_knowledge_catalog_category` (category)
- `idx_knowledge_catalog_clinic` (clinic_id)
- `idx_knowledge_catalog_doi` (doi, WHERE NOT NULL)
- `idx_knowledge_catalog_norm` (norm_number, WHERE NOT NULL)
- `UNIQUE idx_knowledge_catalog_unique_doi` (doi, WHERE NOT NULL AND != '')
- `UNIQUE idx_knowledge_catalog_unique_url` (source_url, WHERE NOT NULL AND != '')

### knowledge_monitors

**Migration:** `017_knowledge_monitors.sql`

| Campo | Tipo | Descricao |
|---|---|---|
| `id` | `SERIAL PK` | ID unico |
| `clinic_id` | `INT` | Tenant (default 1) |
| `name` | `VARCHAR(255)` | Nome descritivo do monitor |
| `url` | `TEXT` | URL da fonte |
| `source_type` | `VARCHAR(50)` | `rss`, `html_page`, `pubmed_query`, `anvisa`, `dou` |
| `search_query` | `TEXT` | Termos de busca (PubMed) ou CSS selector (HTML) |
| `check_interval_hours` | `INT` | Intervalo de verificacao (default 24h) |
| `max_items` | `INT` | Max items por check (default 10) |
| `is_active` | `BOOLEAN` | Ativo/inativo |
| `last_checked_at` | `TIMESTAMPTZ` | Ultimo check |
| `last_hash` | `VARCHAR(64)` | Hash do ultimo conteudo visto |
| `items_found` | `INT` | Total de items encontrados historicamente |
| `created_by` | `INT` | ID do usuario que criou |

**Monitors seed (pre-configurados):**

| Nome | Tipo | Query | Intervalo |
|---|---|---|---|
| PubMed - CBD Therapeutic | `pubmed_query` | `cannabidiol therapeutic systematic review` | 24h |
| PubMed - Cannabis Pain | `pubmed_query` | `medical cannabis chronic pain clinical trial` | 24h |
| PubMed - CBD Epilepsy | `pubmed_query` | `cannabidiol epilepsy treatment` | 48h |
| PubMed - THC Safety | `pubmed_query` | `THC safety pharmacokinetics dosage` | 48h |
| PubMed - Cannabis Anxiety | `pubmed_query` | `cannabis anxiety disorder randomized` | 48h |
| ANVISA - Cannabis Portal | `html_page` | (pagina inteira) | 72h |
| DOU - Resolucoes ANVISA | `html_page` | `anvisa cannabis` | 24h |
| Planalto - Lei de Drogas | `html_page` | (pagina inteira) | 168h (7 dias) |

---

## Endpoints da API

### /api/v1/knowledge/*

**Arquivo:** `src/web/routes/knowledge.py`  
**Blueprint:** `knowledge_bp`  
**Prefix:** `/api/v1/knowledge`

| Metodo | Rota | Roles | Descricao |
|---|---|---|---|
| `GET` | `/catalog` | Admin, Medico | Lista documentos do catalogo (paginado, filtravel por doc_type/source/status/search) |
| `GET` | `/catalog/<doc_id>` | Admin, Medico | Detalhes de um documento |
| `POST` | `/auto-search` | Admin, Medico | Dispara busca automatica PubMed + legislacao |
| `POST` | `/search-pubmed` | Admin, Medico | Busca PubMed por query especifica |
| `POST` | `/classify` | Admin, Medico | Classifica documento por tipo |
| `GET` | `/stats` | Admin, Medico | Estatisticas da base de conhecimento (por tipo, source, storage, status + ChromaDB chunks + Google Files count) |
| `GET` | `/monitors` | Admin, Medico | Lista todos os monitors |
| `POST` | `/monitors` | Admin | Cria novo monitor |
| `PATCH` | `/monitors/<monitor_id>` | Admin | Ativa/desativa monitor |
| `POST` | `/monitors/run` | Admin, Medico | Executa todos os monitors pendentes |

**Nota:** Todos os `POST`/`PATCH` requerem CSRF token JSON (`_require_json_csrf()`).

### /api/v1/regulatory/*

**Arquivo:** `src/web/routes/regulatory.py`  
**Blueprint:** `regulatory_bp`  
**Prefix:** `/api/v1/regulatory`

| Metodo | Rota | Roles | Descricao |
|---|---|---|---|
| `GET` | `/files` | Admin, Medico | Lista arquivos de legislacao enviados ao Google Files API |
| `POST` | `/upload` | Admin | Envia todos os PDFs de `data/legislation/` para Google Files API |
| `POST` | `/query` | Admin, Medico | Consulta legislacao com contexto completo (texto ou JSON estruturado) |

**Parametros de `/query`:**
- `question` (obrigatorio): Pergunta sobre legislacao
- `files` (opcional): Lista de nomes de arquivos especificos
- `structured` (bool): Se `true`, retorna JSON com citations (`query_legislation_structured`)

---

## Seguranca e LGPD

### O que NUNCA vai para o MemPalace

| Dado | Motivo |
|---|---|
| CPF / CNPJ | PII — sanitizado via regex |
| Telefone | PII — sanitizado via regex |
| Email | PII — sanitizado via regex |
| Endereco | PII — sanitizado via regex |
| Nome completo do paciente | PII — sanitizado via regex |

### O que fica no PostgreSQL (com Fernet encryption)

| Dado | Tabela |
|---|---|
| Nome do paciente | `patients` |
| Telefone WhatsApp | `patients` |
| Historico medico detalhado | `medical_history` |
| Planos de tratamento com dosagens | `treatment_plans` |
| Relatorios de anamnese | `anamnesis_reports` |

### O que vai para o MemPalace (anonimizado)

| Dado | Exemplo |
|---|---|
| Padroes clinicos | "Fibromialgia feminino 50a — CBD 20:1 eficaz" |
| Outcomes | "[OK] prescritor duration=3200ms confidence=0.87" |
| Fatos do knowledge graph | "CBD_20:1 -> eficaz_para -> fibromialgia" |
| Falhas | "[FAIL] cientifico error=ChromaDB connection timeout" |

---

## Custos Estimados

### Tokens por Execucao (estimativa)

| Agente | LLM | Input Tokens | Output Tokens | Custo/exec (USD) |
|---|---|---|---|---|
| Triagem | GPT-4 | ~800 | ~400 | ~$0.018 |
| Anamnese | GPT-4 | ~1,200 | ~600 | ~$0.027 |
| Prescritor | GPT-4 | ~1,500 | ~800 | ~$0.035 |
| Cientifico (RAG) | Gemini 1.5 Flash | ~2,000 + chunks | ~1,000 | ~$0.001 |
| Cientifico (fallback) | GPT-4o-mini | ~1,500 | ~800 | ~$0.002 |
| Regulatorio (compliance) | Nenhum | 0 | 0 | $0.000 |
| Regulatorio (query) | Gemini 2.0 Flash | ~10,000+ (docs) | ~500 | ~$0.003 |
| FollowUp | Nenhum | 0 | 0 | $0.000 |
| Extrator | Nenhum | 0 | 0 | $0.000 |

### Custo por Chain (estimativa)

| Chain | Custo estimado |
|---|---|
| Diagnostico Completo (5 agents) | ~$0.08 - $0.12 |
| Prescricao Segura (3 agents) | ~$0.06 - $0.08 |
| Follow-up Inteligente (1-2 agents) | $0.00 - $0.04 |
| Ingestao de Conhecimento | $0.00 (APIs publicas) |

### Comparativo de Modelos

| Modelo | Uso no sistema | Input ($/1M tokens) | Output ($/1M tokens) |
|---|---|---|---|
| GPT-4 | Triagem, Anamnese, Prescritor | $30.00 | $60.00 |
| GPT-4o-mini | Cientifico (fallback) | $0.15 | $0.60 |
| Gemini 1.5 Flash | Cientifico (RAG) | $0.075 | $0.30 |
| Gemini 2.0 Flash | Regulatorio (Google Files) | $0.10 | $0.40 |

**Nota:** Precos de referencia sujeitos a alteracao. O sistema prioriza Gemini para operacoes de alto volume (RAG, legislacao) e reserva GPT-4 para decisoes clinicas criticas (triagem, prescricao).
