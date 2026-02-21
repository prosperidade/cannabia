# AI_MODULE_DOCUMENTATION.md

## 1) Purpose of the AI Module

The AI module converts anamnesis input into three structured medical-support artifacts:

1. Clinical analysis
2. Treatment plan
3. Scientific report

It is designed to be deterministic in shape (JSON schema enforced) and auditable (every call logged).

---

## 2) End-to-End AI Flow

```text
Client POST /ai/test (JSON)
        |
        v
CannabIAService.process_patient_case
  |- attach request context (request_id, user_id)
  |- resolve/create patient_id
  |- security check (prompt injection patterns)
  |- schema validation (Pydantic AnamnesisInput)
  |- execute CannabIAPipeline (3 stages)
  |- aggregate token usage
  |- estimate cost via pricing table
  |- persist ai_audit_logs row
        |
        v
Structured JSON response
```

---

## 3) Module Components

## 3.1 `ai/service.py`

Responsibilities:

- Orchestrates complete processing lifecycle.
- Handles three classes of failures separately:
  - security block
  - validation error
  - execution/runtime error
- Writes audit log row in all branches.

Design decision:

- Audit logging is not optional; this supports medical/compliance traceability.

## 3.2 `ai/pipeline.py`

Pipeline stages:

1. `run_clinical_analysis`
2. `run_treatment_plan`
3. `run_scientific_report`

Each stage returns validated schema object + token usage metadata.

Pipeline output includes:

- structured outputs for each stage
- combined token usage (`input`, `output`, `total`)

## 3.3 `ai/chains.py`

Responsibilities:

- calls OpenAI chat completions API
- enforces JSON-only output contract
- parses JSON
- validates result with Pydantic model

Why strict schema validation matters:

- Prevents downstream code from consuming malformed AI output.
- Converts LLM uncertainty into explicit validation failures.

## 3.4 `ai/prompts.py`

Contains stage-specific prompt templates with:

- strict format requirements
- explicit “JSON only” constraints
- contextual patient/treatment data injection

## 3.5 `ai/schemas.py`

Pydantic contracts:

- `AnamnesisInput`
- `ClinicalAnalysis`
- `TreatmentPlan`
- `ScientificReport`

These contracts are the source of truth for field shape and types.

## 3.6 `ai/validators.py`

Security and normalization utilities:

- regex-based prompt injection pattern detection
- payload normalization (string clipping, list normalization)
- schema validation helper

Current service path uses security check + direct schema validation; normalization helper exists for future hardening workflows.

## 3.7 `ai/pricing.py`

Contains static per-1k token pricing for model(s) and calculates estimated request cost.

---

## 4) AI Audit Logs: What Is Recorded and Why

The audit repository stores:

- identity context (`user_id`, `patient_id`, `request_id`)
- endpoint
- serialized input/output payloads
- status and error message
- model metadata (`model`, `prompt_version`, `prompt_hash`)
- token usage (`input/output/total`)
- timing fields
- estimated USD cost

Why this is critical:

1. Clinical traceability: understand what AI generated for whom.
2. Operational observability: find failing patterns.
3. Cost governance: monitor token consumption and budget usage.
4. Security/compliance: detect abuse or suspicious prompt patterns.

---

## 5) Token Usage Tracking

Token tracking works by reading usage metadata from OpenAI response per stage:

- prompt tokens (input)
- completion tokens (output)
- total tokens

Pipeline sums all three stages:

```text
total_input_tokens  = s1.input + s2.input + s3.input
total_output_tokens = s1.output + s2.output + s3.output
total_tokens        = s1.total + s2.total + s3.total
```

These values are persisted in `ai_audit_logs` for reporting.

---

## 6) Cost Tracking Logic

Cost estimation formula:

```text
input_cost  = (input_tokens / 1000) * input_per_1k
output_cost = (output_tokens / 1000) * output_per_1k
total_cost  = round(input_cost + output_cost, 6)
```

Current model pricing table includes `gpt-4o-mini`.

Practical note for juniors:

- This is an estimate based on configured rates.
- If provider pricing changes and code table is not updated, estimates drift from invoice reality.

---

## 7) AI Security Considerations

## 7.1 Prompt Injection Defense

Current defense:

- Input fields are concatenated and matched against known suspicious regex patterns.

This is helpful but not sufficient alone. Defense-in-depth should include:

- stricter context isolation
- output schema enforcement (already present)
- safe logging policies
- policy-based post-validation before persisting or acting

## 7.2 PHI Handling in AI Context

AI input/output payloads can contain sensitive medical information.

Safety principles:

- avoid raw payload logs outside audit-controlled context
- restrict access to AI audit dashboards
- define retention and deletion policy
- encrypt backups at rest

## 7.3 Failure Handling

Service intentionally distinguishes failure categories and records each:

- `security_blocked`
- `validation_error`
- `error`
- `success`

This allows measurable security and data quality monitoring.

---

## 8) Secure vs Insecure AI Usage Patterns

### Secure pattern

```text
Validate input -> enforce schema -> run pipeline -> validate outputs -> audit log -> respond
```

### Insecure pattern

```text
Send raw user text directly to model -> trust free-text output -> no logging
```

The insecure path is dangerous in medical systems because it is untraceable and brittle.

---

## 9) How to Add a New AI Stage Safely

1. Define new Pydantic output schema.
2. Add explicit prompt template with strict JSON format.
3. Implement chain runner with parse + schema validation.
4. Add stage to pipeline and token aggregation.
5. Extend audit schema/logging fields if needed.
6. Update metrics dashboards/queries.
7. Update this documentation.

---

## 10) Glossary

- **Prompt injection**: malicious instruction attempting to override intended model behavior.
- **Schema validation**: checking AI output matches required structure.
- **Token**: billing/processing unit used by language models.
- **Telemetry**: metrics and traces about runtime behavior.
- **Audit log**: immutable-like record of actions and outcomes.
