# AI MODULE DOCUMENTATION — CannabIA

> **Módulo:** `src/ai/`
> **Modelos utilizados:** `gpt-4o-mini` (OpenAI) · `gemini-1.5-flash` (Google)
> **RAG:** ChromaDB + `text-embedding-004` (Google)
> **Auditoria:** PostgreSQL (`ai_audit_logs`)

---

## Visão Geral

O módulo de IA do CannabIA implementa um pipeline clínico estruturado em 3 etapas sequenciais para processar casos de pacientes que utilizam Cannabis Medicinal. Cada chamada ao pipeline é integralmente rastreada e persistida no PostgreSQL para fins de auditoria, governança e controle de custos.

---

## Arquitetura do Pipeline

```
Requisição HTTP (POST /ai/test)
        │
        ▼
[CannabIAService.process_patient_case()]
        │
        ├─ Valida contexto de clínica (clinic_id do Flask.g)
        ├─ get_or_create_patient_by_name(clinic_id, patient_name)
        ├─ validate_anamnesis_security(data)    ← Anti prompt injection
        └─ AnamnesisInput(**data)               ← Validação Pydantic
                │
                ▼
       [CannabIAPipeline.run()]
                │
    ┌───────────┼───────────────────────────────┐
    │           │                               │
    ▼           ▼                               ▼
[Etapa 1]   [Etapa 2]                       [Etapa 2.5]
Análise     Plano                        RAG Lookup
Clínica     Terapêutico              ChromaDB + Embedding
(OpenAI)    (OpenAI)                 text-embedding-004
    │           │                               │
    └───────────┴───────────────────────────────┘
                │
                ▼
           [Etapa 3]
       Relatório Científico
       ┌──────────────────┐
       │ Se RAG disponível│ → Gemini 1.5 Flash + contexto vetorial
       │ Se RAG vazio/erro│ → gpt-4o-mini (fallback)
       └──────────────────┘
                │
                ▼
       [save_ai_audit_log()]
    Persiste tudo no PostgreSQL
```

---

## Etapas do Pipeline

### Etapa 1 — Análise Clínica (`run_clinical_analysis`)

**Modelo:** `gpt-4o-mini` (OpenAI)
**Arquivo:** `src/ai/chains.py`

Recebe os dados de anamnese do paciente e produz uma análise clínica estruturada.

**Inputs:**
```python
patient_name: str
age: int
main_complaint: str
symptoms: list[str]
current_medications: list[str]
allergies: list[str]
medical_history: str
```

**Output:** Objeto Pydantic `ClinicalAnalysis` com diagnóstico diferencial, relevância dos sintomas e alertas de segurança.

---

### Etapa 2 — Plano Terapêutico (`run_treatment_plan`)

**Modelo:** `gpt-4o-mini` (OpenAI)
**Arquivo:** `src/ai/chains.py`

Recebe o resultado da Etapa 1 e gera um plano terapêutico com base em Cannabis Medicinal.

**Input:** Objeto `ClinicalAnalysis` da Etapa 1

**Output:** Objeto Pydantic `TreatmentPlan` contendo recomendações de canabinoide, via de administração, dosagem inicial e frequência.

---

### Etapa 2.5 — RAG Lookup (Busca Vetorial)

**Tecnologia:** ChromaDB (local) + Google `text-embedding-004`
**Arquivo:** `src/ai/pipeline.py`, `src/knowledge/`

Antes da geração do Relatório Científico, o sistema busca artigos científicos relevantes no banco vetorial ChromaDB.

**Fluxo:**
1. O `TreatmentPlan` é serializado em JSON
2. O texto é vetorizado com `text-embedding-004` via API Google
3. O ChromaDB retorna os `n=5` chunks mais similares
4. Se o ChromaDB estiver vazio ou a busca falhar, o pipeline continua sem RAG (fallback silencioso)

```python
if self._store.count() > 0:
    query_vec  = self._embedder.embed_query(query_text)
    rag_chunks = self._store.query(query_vec, n_results=5)
    use_rag    = True
else:
    # ChromaDB vazio → fallback para gpt-4o-mini
    use_rag = False
```

---

### Etapa 3 — Relatório Científico

**Caminho RAG:** `run_scientific_report_rag()` → Modelo `gemini-1.5-flash`
**Caminho Fallback:** `run_scientific_report()` → Modelo `gpt-4o-mini`
**Arquivo:** `src/ai/chains.py`

Gera um relatório clínico-científico formatado, citando artigos encontrados pelo RAG (quando disponíveis).

**Output:** Objeto Pydantic `ScientificReport` com justificativa clínica, evidências científicas e recomendações finais.

---

## Segurança e Validação

### Anti Prompt Injection (`src/ai/validators.py`)

Antes de qualquer chamada à IA, o módulo `validate_anamnesis_security()` verifica padrões maliciosos nos dados de entrada.

Se detectado, o pipeline é interrompido, o evento é registrado no `ai_audit_logs` com `status = "security_blocked"`, e uma `ValueError` é elevada.

### Validação Estrutural Pydantic (`src/ai/schemas.py`)

Os dados são validados através do schema `AnamnesisInput` antes de entrar no pipeline. Falhas de validação são registradas com `status = "validation_error"`.

---

## Auditoria e Persistência no PostgreSQL

**Repositório:** `src/repositories/ai_audit_repository.py → save_ai_audit_log()`

Toda execução do pipeline (sucesso, erro, bloqueio de segurança, falha de validação) é persistida na tabela `ai_audit_logs` do PostgreSQL.

### O que é registrado:

| Campo                | O que contém                                         |
|----------------------|------------------------------------------------------|
| `request_id`         | UUID da requisição HTTP (rastreabilidade ponta a ponta) |
| `clinic_id`          | Isolamento multi-tenant                               |
| `patient_id`         | Paciente associado ao processamento                  |
| `user_id`            | Usuário autenticado que disparou a ação              |
| `input_payload`      | JSON completo dos dados de anamnese (PostgreSQL JSONB) |
| `output_payload`     | JSON completo da resposta da IA                      |
| `status`             | `success` / `error` / `validation_error` / `security_blocked` |
| `model`              | Modelo utilizado (`gpt-4o-mini`, `gemini-1.5-flash`) |
| `prompt_version`     | Versão do prompt (ex: `v1.0`)                        |
| `prompt_hash`        | SHA-256 do prompt (integridade)                      |
| `input_tokens`       | Tokens de entrada (custo)                            |
| `output_tokens`      | Tokens gerados (custo)                               |
| `total_tokens`       | Total de tokens                                      |
| `clinical_time_ms`   | Tempo da Etapa 1                                     |
| `treatment_time_ms`  | Tempo da Etapa 2                                     |
| `report_time_ms`     | Tempo da Etapa 3                                     |
| `total_time_ms`      | Tempo total de processamento                         |
| `estimated_cost_usd` | Custo estimado da chamada em USD                     |

---

## Cálculo de Custo (`src/ai/pricing.py`)

A função `calculate_cost(model, input_tokens, output_tokens)` calcula o custo estimado em USD com base nas tabelas de preço dos modelos.

O valor é armazenado em `ai_audit_logs.estimated_cost_usd` como `DECIMAL(10,6)`, permitindo controle granular de custo por clínica, médico ou paciente.

---

## Fluxo de Dados Completo

```
POST /ai/test  ─────────────────────────────────────────────────────────────────┐
     │                                                                           │
     │  {                                                                        │
     │    "patient_name": "João Silva",                                          │
     │    "age": 45,                                                             │
     │    "main_complaint": "dor crônica",                                       │
     │    "symptoms": ["insônia", "ansiedade"],                                  │
     │    "current_medications": ["ibuprofeno"],                                 │
     │    "allergies": [],                                                       │
     │    "medical_history": "fibromialgia"                                      │
     │  }                                                                        │
     ▼                                                                           │
CannabIAService                                                                  │
     ├─ [PostgreSQL] INSERT/SELECT patients → patient_id                         │
     ├─ [validator] security check                                               │
     ├─ [pydantic] schema validation                                             │
     └─ CannabIAPipeline.run()                                                   │
           ├─ [OpenAI]   Etapa 1 → ClinicalAnalysis                              │
           ├─ [OpenAI]   Etapa 2 → TreatmentPlan                                 │
           ├─ [ChromaDB] Etapa 2.5 → rag_chunks[]                               │
           └─ [Gemini]   Etapa 3 → ScientificReport                             │
                │                                                                │
                ▼                                                                │
     [PostgreSQL] INSERT ai_audit_logs  ◄──────────────────────────────────────┘
           {clinic_id, patient_id, tokens, cost, payload...}
                │
                ▼
          HTTP 200 Response
     {clinical_analysis, treatment_plan, scientific_report}
```

---

## Variáveis de Ambiente Necessárias

| Variável        | Usado em                     | Descrição               |
|-----------------|------------------------------|-------------------------|
| `OPENAI_API_KEY` | Etapas 1, 2 e fallback Etapa 3 | Chave OpenAI          |
| `GOOGLE_API_KEY` | Embedding (RAG) e Etapa 3 RAG  | Chave Google AI       |
| `DATABASE_URL`  | `save_ai_audit_log()`        | Conexão com PostgreSQL  |
