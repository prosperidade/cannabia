# AI_MODULE_DOCUMENTATION.md

## 1) Module Purpose

The AI module transforms a structured anamnesis payload into structured clinical support outputs.

It is designed around:

- schema-validated inputs,
- schema-validated outputs,
- deterministic stage sequencing,
- audit logging with tokens/costs,
- explicit error classification.

---

## 2) Endpoint Entry Point

AI processing is exposed through:

- `POST /ai/test`

Request requirements:

- authenticated session,
- JSON body,
- required fields for anamnesis schema.

If request is not JSON, route returns HTTP 400.

---

## 3) End-to-End Flow

```text
Client POST /ai/test
   |
   v
Route handler in app.py
   |
   v
CannabIAService.process_patient_case(data)
   |- read g.request_id and g.user_id
   |- validate patient_name exists
   |- resolve/create patient_id
   |- validate_anamnesis_security(payload)
   |- validate schema (AnamnesisInput)
   |- pipeline.run(anamnesis)
   |- compute token totals
   |- calculate estimated cost
   |- save_ai_audit_log(...)
   v
JSON response
```

---

## 4) AI Pipeline Stages

`CannabIAPipeline.run` executes three ordered stages:

1. **Clinical analysis**
2. **Treatment plan**
3. **Scientific report**

Each stage:

- sends prompt to model,
- receives JSON response,
- parses JSON,
- validates with corresponding Pydantic schema,
- returns token usage metadata.

---

## 5) Prompt and Output Contract

Prompt templates enforce strict formatting instructions:

- “return only valid JSON”,
- no markdown,
- no text outside JSON.

Output schemas:

- `ClinicalAnalysis`
- `TreatmentPlan`
- `ScientificReport`

If model output is invalid JSON or schema-incompatible, execution fails and is treated as an error condition.

---

## 6) Input Validation and Security

Before model execution, service performs two major checks:

1. **Security check** via `validate_anamnesis_security`:
   - scans flattened input text against prompt-injection pattern regex list.
2. **Schema validation** via `AnamnesisInput`:
   - ensures required fields and expected types.

Failure outcomes:

- security failure -> status `security_blocked` in audit logs,
- schema failure -> status `validation_error` in audit logs.

---

## 7) AI Audit Logging Behavior

Audit rows are inserted through `save_ai_audit_log`.

Recorded dimensions include:

- request context (`request_id`, `user_id`, `endpoint`),
- business context (`patient_id`),
- payloads (`input_payload`, `output_payload`),
- status and error text,
- model and prompt metadata,
- token usage fields,
- timing fields,
- estimated cost.

Audit logging is executed in success and failure branches, improving traceability.

---

## 8) Token Usage Tracking

Model API response usage fields are extracted per stage:

- `prompt_tokens`
- `completion_tokens`
- `total_tokens`

Pipeline aggregates totals:

```text
input_total  = stage1.input + stage2.input + stage3.input
output_total = stage1.output + stage2.output + stage3.output
total_total  = stage1.total + stage2.total + stage3.total
```

These totals are stored in audit logs and surfaced by dashboard summaries.

---

## 9) Cost Estimation

Cost is estimated in `src/ai/pricing.py` from static per-1k rates:

```text
input_cost  = (input_tokens / 1000) * input_per_1k
output_cost = (output_tokens / 1000) * output_per_1k
estimated_cost = round(input_cost + output_cost, 6)
```

Current configured model pricing map contains `gpt-4o-mini`.

If model key is missing in pricing map, cost defaults to `0.0`.

---

## 10) AI Metrics and Dashboards

Two read models consume AI audit data:

1. `get_ai_audit_summary()`
   - total successful requests,
   - sum of tokens,
   - sum of estimated cost.

2. `get_recent_ai_logs(limit)`
   - recent records with status/tokens/cost/timestamp.

UI routes:

- `/ai-audit`
- `/admin/ai-metrics`

---

## 11) Error Model and User-Facing Behavior

At route level:

- `ValueError` -> HTTP 400 with error message.
- uncaught exceptions -> HTTP 500 with generic message.

Inside service:

- runtime processing errors are logged and re-raised as generic runtime error text.

This pattern avoids exposing sensitive internals directly to clients.

---

## 12) AI Security Considerations

### Sensitive data handling

- Input/output payloads can contain medical data.
- Access to audit views should remain restricted.
- Redaction strategy should be considered for broader logs outside audit table.

### Prompt injection handling

Regex-based detection blocks common attack wording, but should be treated as one defense layer.

### Operational monitoring

Track spikes in:

- `security_blocked` rates,
- validation failures,
- token cost anomalies,
- runtime error rates.

---

## 13) Sequence Diagram (ASCII)

```text
User -> Flask /ai/test -> CannabIAService
CannabIAService -> patient_repository (get_or_create_patient_by_name)
CannabIAService -> validators (security + schema)
CannabIAService -> pipeline
pipeline -> chains -> OpenAI API
OpenAI API -> chains (JSON + usage)
pipeline -> CannabIAService (outputs + token totals)
CannabIAService -> pricing.calculate_cost
CannabIAService -> ai_audit_repository.save_ai_audit_log
CannabIAService -> Flask response JSON
```

---

## 14) Glossary

- **Prompt injection**: malicious attempt to alter model instructions.
- **Schema validation**: strict structural/type checking of data.
- **Token**: billing and context unit used by LLM providers.
- **Audit log**: persistent event record for accountability.
- **Estimated cost**: computed approximation from token totals and configured pricing.
