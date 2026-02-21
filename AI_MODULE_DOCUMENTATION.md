# AI_MODULE_DOCUMENTATION.md

## 1) Purpose

The AI module receives structured anamnesis input and returns three structured outputs for clinical support:

1. clinical analysis,
2. treatment plan,
3. scientific report.

The design emphasizes deterministic schema validation and auditability.

---

## 2) Entry Point and Contract

### HTTP entrypoint

- `POST /ai/test`

### Input contract

- request must be JSON,
- payload must satisfy `AnamnesisInput` schema,
- `patient_name` is mandatory,
- security validator checks for prompt-injection patterns.

### Output contract

JSON response includes:

- `clinical_analysis`
- `treatment_plan`
- `scientific_report`
- `token_usage`

---

## 3) End-to-End Processing Flow

```text
Client
  -> POST /ai/test
     -> CannabIAService.process_patient_case
        -> request/user context capture
        -> patient resolve/create
        -> input security validation
        -> Pydantic schema validation
        -> CannabIAPipeline.run
           -> stage 1: run_clinical_analysis
           -> stage 2: run_treatment_plan
           -> stage 3: run_scientific_report
        -> token aggregation
        -> cost calculation
        -> AI audit persistence
  <- JSON response
```

---

## 4) Module Responsibilities by File

## 4.1 `src/ai/service.py`

Responsibilities:

- orchestration of validation + pipeline + auditing,
- classification of failure types,
- mapping request context (`g.request_id`, `g.user_id`) into audit logs.

Main statuses written to audit logs:

- `success`
- `security_blocked`
- `validation_error`
- `error`

## 4.2 `src/ai/pipeline.py`

Responsibilities:

- execute the 3-stage generation chain,
- aggregate stage token usage into one combined structure.

## 4.3 `src/ai/chains.py`

Responsibilities:

- call OpenAI Chat Completions API,
- enforce JSON-only response handling,
- parse raw JSON,
- validate against stage schema,
- return usage counters from provider response.

## 4.4 `src/ai/schemas.py`

Pydantic schema contracts for input and outputs.

## 4.5 `src/ai/validators.py`

Security helper for prompt-injection detection and payload normalization utilities.

## 4.6 `src/ai/pricing.py`

Static model pricing map and estimated cost calculation function.

---

## 5) Stage Details

### Stage 1: Clinical Analysis

- Prompt uses anamnesis fields.
- Output validated as `ClinicalAnalysis`.

### Stage 2: Treatment Plan

- Prompt uses serialized clinical analysis output.
- Output validated as `TreatmentPlan`.

### Stage 3: Scientific Report

- Prompt uses serialized treatment plan output.
- Output validated as `ScientificReport`.

All stage prompts instruct model to return only JSON.

---

## 6) AI Audit Logging

Audit rows are persisted through `save_ai_audit_log` with fields that support traceability and cost governance:

- actor/request context (`user_id`, `request_id`, endpoint),
- patient context (`patient_id`),
- input and output payload snapshots,
- status and error description,
- model metadata (`model`, `prompt_version`, `prompt_hash`),
- token usage counters,
- timing fields,
- estimated USD cost.

This means both successful and failed runs are observable.

---

## 7) Token Usage Tracking

Per-stage usage received from provider:

- prompt/input tokens,
- completion/output tokens,
- total tokens.

Pipeline computes totals:

```text
total_input_tokens  = stage1.input + stage2.input + stage3.input
total_output_tokens = stage1.output + stage2.output + stage3.output
total_tokens        = stage1.total + stage2.total + stage3.total
```

These totals are stored in audit logs and consumed by dashboard metrics.

---

## 8) Cost Estimation

Cost is estimated by model pricing table using per-1k rates.

Formula:

```text
input_cost  = (input_tokens / 1000) * input_per_1k
output_cost = (output_tokens / 1000) * output_per_1k
estimated_cost = round(input_cost + output_cost, 6)
```

Current pricing map includes `gpt-4o-mini`.

---

## 9) Security Model for AI Endpoint

### 9.1 Prompt-injection defense

Security validator scans input text against suspicious instruction patterns (regex-based).

### 9.2 Structural validation

Pydantic input schema rejects malformed payloads before model execution.

### 9.3 Output validation

Model output is accepted only when valid JSON matching expected schema.

### 9.4 Error handling strategy

- client receives controlled error responses,
- detailed failure state is persisted in audit table.

---

## 10) Dashboards and Reporting

AI dashboards consume repository queries:

- summary metrics: successful requests, token sum, cost sum,
- recent log list: latest status/tokens/cost entries.

Routes:

- `/ai-audit`
- `/admin/ai-metrics`

---

## 11) Secure vs Insecure Patterns

### Secure pattern

```text
Validate input security -> validate schema -> run staged pipeline -> validate output schema -> persist audit metadata
```

### Insecure pattern

```text
Send raw free-text directly to model -> accept unvalidated output -> no persistent audit record
```

---

## 12) Sequence Diagram

```text
User -> /ai/test -> Flask route
Flask route -> CannabIAService
CannabIAService -> patient_repository
CannabIAService -> validators
CannabIAService -> pipeline
pipeline -> chains -> OpenAI
OpenAI -> chains (json+usage)
pipeline -> CannabIAService (staged outputs + totals)
CannabIAService -> pricing
CannabIAService -> ai_audit_repository
CannabIAService -> Flask response
```

---

## 13) Glossary

- **Prompt injection**: malicious instruction attempting to override intended model behavior.
- **Schema validation**: strict data shape/type verification.
- **Token**: unit used for model processing and billing.
- **Audit log**: persistent event record for accountability and analysis.
- **Estimated cost**: calculated approximation based on token counts.
