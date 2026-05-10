# Backlog AgentePrescritor — Dívidas técnicas registradas

> **Origem:** Sprint 1 Track C.1 + C.3. Criado em 2026-05-10 quando o AgentePrescritor entrou no clinical_flow como 4º stage (Anamnese → Tratamento → Prescritor → Cientifico).
> **Decisão arquitetural Q-C1:** Prescritor APÓS Tratamento e ANTES de Cientifico. Cientifico continua consumindo `treatment_plan` (zero refactor). Flow retorna `treatment_plan` E `prescription_result` em paralelo.

## Princípio: catalogar conservadoramente, expandir baseado em uso real

A primeira versão do Prescritor cobre o subset de condições e drogas que aparecem com mais frequência nos atendimentos piloto. Expansões devem ser priorizadas por dado real (logs de defaults_used, cyp450_interactions vazias quando deveriam pegar) — não por especulação clínica genérica.

---

## Estado atual (Sprint 1 — entrega C.1)

### Pipeline em produção

```
Anamnese (gpt-4o-mini)
   ↓ clinical_analysis: probable_conditions, risk_level, ...
Tratamento (gpt-4o-mini)
   ↓ treatment_plan: cannabinoid_ratio (draft), suggested_dosage, ...
Prescritor (Rules Engine + gpt-4o-mini @ temperature=0 + Safety Clamp)
   ↓ prescription_result: final_dosage clampada + signals + summary
Cientifico (Gemini 1.5 Flash quando RAG ativo, gpt-4o-mini fallback)
   ↓ scientific_report (consome treatment_plan, NÃO prescription_result)
```

### Catálogo Rules Engine — cobertura

#### Condições com protocolo determinístico (13)

Definidas em [src/ai/prescriber.py:81-130](../src/ai/prescriber.py#L81-L130) — `CONDITION_PROTOCOLS`:

| Condição | Ratio CBD:THC | mg/kg/dia | Espectro | Via |
|---|---|---|---|---|
| epilepsia | 20:1 | 2.5 | full_spectrum | sublingual |
| dor cronica | 1:1 | 0.5 | full_spectrum | sublingual |
| dor neuropatica | 3:1 | 0.5 | full_spectrum | sublingual |
| ansiedade | CBD puro | 0.5 | broad_spectrum | sublingual |
| insonia | 10:1 | 0.5 | full_spectrum | sublingual |
| fibromialgia | 3:1 | 0.5 | full_spectrum | sublingual |
| parkinson | 10:1 | 1.0 | full_spectrum | sublingual |
| esclerose multipla | 1:1 | 0.3 | full_spectrum | sublingual |
| autismo | 20:1 | 1.0 | broad_spectrum | sublingual |
| tept | 5:1 | 0.5 | full_spectrum | sublingual |
| crohn | 5:1 | 0.3 | full_spectrum | oral |
| nausea | 1:3 | 0.2 | full_spectrum | sublingual |
| **fallback** | **ansiedade** (CBD puro, baixa dose) | — | — | — |

#### Interações CYP450 cobertas (11)

Definidas em [src/ai/prescriber.py:134-179](../src/ai/prescriber.py#L134-L179) — `CYP450_INTERACTIONS`:

`varfarina, clobazam, valproato, carbamazepina, fenitoina, fluoxetina, sertralina, omeprazol, tramadol, morfina, metformina`

Cada entrada tem `warning` humanamente legível + `dose_multiplier` (0.5 a 1.0) que afeta `initial_rate` e `max_cbd`.

#### Granularidade do Safety Clamp

Aplicada em [src/ai/prescriber.py:253-324](../src/ai/prescriber.py#L253-L324) — `calculate_safety_limits` + `_clamp_recommendation`:

- ✅ **Ajuste por idade**: `<12` (pediátrico, dose mínima), `12-17` (adolescente, dose reduzida), `18-65` (adulto, padrão), `>65` (geriátrico, conservador).
- ✅ **Cap por peso**: `max_cbd = min(weight_kg * X, hard_cap)` onde X varia por faixa etária e hard_cap é 600-1500mg/dia.
- ✅ **Naive vs experiente**: paciente sem uso prévio recebe `initial_rate * 0.5`.
- ✅ **Multiplicador por interação CYP450**: aplica `min()` dos multipliers detectados.
- ✅ **Risk_level alto**: adiciona warning de monitoramento intensivo.
- ✅ **Contraindicações detectadas** (texto livre match): esquizofrenia, psicose, gestante/grávida, lactante/amamentando, insuficiência hepática, hepatopatia.
- ✅ **Confidence cap**: `confidence_score ≤ 0.5` se contraindicação; `≤ 0.6` se interação.

---

## Dívida 1 — Expandir catálogo de condições

**Sprint alvo:** 3 (média prioridade — Sprint 2 prioriza prompt_registry/paginação/Sentry per anchor).

**Razão:** ampliar a tabela é trabalho clínico que precisa revisão por médico externo, não apenas código. Não bloqueia produção (fallback "ansiedade" cobre casos não mapeados, com confidence_score baixo sinalizando revisão obrigatória).

**Falta catalogar (top 10 por prevalência clínica esperada no piloto)**:

1. glaucoma
2. doença de Alzheimer (estágios iniciais)
3. ELA (esclerose lateral amiotrófica)
4. anorexia em câncer / wasting
5. espasticidade pós-AVC
6. síndrome de Tourette
7. doença de Huntington
8. fibrose cística (sintomas inflamatórios)
9. síndrome de Dravet (sub-tipo de epilepsia, protocolo distinto)
10. AIDS-wasting

**Métrica para priorizar:** registrar em telemetria quantas vezes `_match_condition` cai no fallback `"ansiedade"` por mês. Top 5 condições subjacentes detectadas via análise de `main_complaint` viram a primeira leva.

---

## Dívida 2 — Expandir matriz de interações CYP450

**Sprint alvo:** 3 (mesma janela da Dívida 1).

**Falta catalogar** (alta prevalência + interação real documentada):

- **Anticoagulantes/antiplaquetários:** rivaroxabana, apixabana, dabigatrana, clopidogrel.
- **Psicotrópicos (ISRS/ISRSN/BZD):** paroxetina, escitalopram, venlafaxina, alprazolam, clonazepam, diazepam.
- **Anticonvulsivantes adicionais:** fenobarbital, topiramato, lamotrigina, levetiracetam.
- **Endocrino/metabólico:** levotiroxina, sinvastatina, atorvastatina, rosuvastatina.
- **Imunossupressores:** ciclosporina, tacrolimus.
- **Cardiovasculares:** amiodarona, propranolol, metoprolol.
- **Antimicrobianos:** claritromicina, eritromicina, cetoconazol, fluconazol, rifampicina.
- **Antirretrovirais:** ritonavir, efavirenz.

**Estratégia recomendada:** importar matriz da [Drug Interaction Database](https://www.drugbank.ca/) (ou equivalente nacional regulado) ao invés de manter dict hardcoded. Já é o caminho natural para Sprint 3+ porque a matriz cresce rápido.

---

## Dívida 3 — Granularidade de safety clamp por co-fator clínico

**Sprint alvo:** 3 — exige expansão de `DosageInput` schema + UI da anamnese.

**Falta cobrir**:

- **Função hepática (Child-Pugh A/B/C)** — escalar dose conforme. Hoje só detecta texto "insuficiência hepática" como contraindicação binária.
- **Função renal** — clearance de creatinina <30 mL/min reduz CBD significativamente.
- **IMC** — sub-peso (<18.5) e obesidade extrema (>35) mudam farmacocinética; clamp atual usa peso bruto.
- **Sexo** — mulheres metabolizam THC mais rápido (literatura: clearance 30% maior); ratio inicial pode ser ajustado.
- **Idade pediátrica granular** — `<2 anos` exige protocolo separado (atualmente entra no balde `<12`).
- **Polifarmácia** — `current_medications.length >= 5` deveria gerar flag adicional independente de match CYP450.
- **Comorbidades cardio** — arritmia, IC com FE reduzida → THC contraindicação relativa não detectada hoje.

---

## Dívida 4 — `AnamnesisInput` não coleta `weight_kg` nem `prior_cannabis_use`

**✅ FECHADA na Sprint 2 (Track AI — branch `feat/sprint-2-AI-anamnesis-extension`)**

**Surpresa do Phase 0:** o wizard de triagem (`step-dados-fisicos.tsx` + `types-triagem.ts`) JÁ coletava peso/altura/uso prévio. O bug não era ausência de UI, era propagação: `triage_intake_service.py:190-198` extraía os 3 campos das linhas 185-187 mas dropava-os ao construir `AnamnesisInput`. Resultado: `dosage_defaults_used=True` em 100% dos atendimentos.

**Trabalho realizado:**

1. ✅ `src/ai/schemas.py` — `AnamnesisInput` recebeu `weight_kg: Optional[float]` (ge=1.0/le=300.0), `height_cm: Optional[float]` (ge=30.0/le=250.0), `prior_cannabis_use: Optional[bool]`.
2. ✅ `src/services/triage_intake_service.py` — construtor `AnamnesisInput(...)` agora passa os 3 campos extraídos do payload.
3. ✅ `src/services/anamnesis_flow.py` (WhatsApp) — passa `None` explícito (WhatsApp ainda não coleta; back-compat com defaults conservadores).
4. ✅ `src/ai/clinical_flow.py:87-92` — defaults conservadores (`DOSAGE_DEFAULT_WEIGHT_KG=70.0`, `DOSAGE_DEFAULT_PRIOR_USE=False`) mantidos como fallback. `defaults_used` continua usando `or` (qualquer campo `None` mantém badge).
5. ✅ Frontend tooltip atualizado em `frontend/app/atendimentos/[id]/page.tsx`.
6. ✅ Tests: regression (`test_build_triage_payload_propagates_physical_data_to_anamnesis_input`) + happy path (`test_dosage_defaults_used_false_when_anamnesis_complete`).

**Resultado clínico:** quando wizard de triagem alimenta os 3 campos, `dosage_defaults_used=False` e o Prescritor calcula com peso/uso reais. Atendimentos via WhatsApp continuam exibindo o badge (gap de UI, não código).

**Diagnóstico histórico (mantido para auditoria):** [src/ai/schemas.py](../src/ai/schemas.py) `AnamnesisInput` tinha só: `patient_name`, `age`, `main_complaint`, `symptoms`, `current_medications`, `allergies`, `medical_history`. Sem peso, sem altura, sem histórico de uso prévio de cannabis. [src/ai/clinical_flow.py:87-91](../src/ai/clinical_flow.py#L87-L91) aplicava defaults conservadores:

```python
DOSAGE_DEFAULT_WEIGHT_KG = 70.0   # adulto médio
DOSAGE_DEFAULT_PRIOR_USE = False  # naive (halve initial dose)
```

**Impacto clínico (pré-fix):** dosagem inicial sub-otimizada para pacientes muito magros/pesados; pacientes experientes recebiam dose halved desnecessariamente. UI mostrava badge "Dosagem com defaults conservadores" sinalizando ao médico que deveria ajustar manualmente.

---

## Dívida 5 — `safety_clamp_applied` é heurística, não comparação raw vs clamped

**Sprint alvo:** 4 ou opcional (baixa prioridade — heurística atual é honesta).

**Diagnóstico:** [src/ai/agents/prescritor.py:execute](../src/ai/agents/prescritor.py) deriva `safety_clamp_applied` de `bool(cyp450_interactions or contraindications)`. Não compara `recommendation` LLM-raw vs `recommendation` pós-`_clamp_recommendation` porque [src/ai/prescriber.py:run_prescriber](../src/ai/prescriber.py) não expõe a versão pré-clamp.

**Caso edge:** se LLM gerou dose dentro dos limites E não há interações/contraindicações detectadas, `safety_clamp_applied=False` mesmo que o clamp tenha sido executado (sem efeito). Para badge UI isso é correto (não há ajuste a sinalizar). Para audit forense detalhado, falta o sinal.

**Trabalho:** se necessário, refatorar `run_prescriber()` para retornar tupla `(clamped, raw, limits, tokens)` e comparar antes de derivar a flag. Não bloqueante.

---

## Dívida 6 — Cientifico não cita evidência da `final_dosage`

**Sprint alvo:** 2 ou 3 (depende do feedback de uso).

**Diagnóstico:** Cientifico continua consumindo `treatment_plan` (draft do Tratamento), não `prescription_result.final_dosage`. Isso significa que `scientific_report.references` pode citar evidência para o ratio do draft (10:1) enquanto `final_dosage.cannabinoid_ratio` foi clampado para outro (20:1). Inconsistência potencial.

**Trabalho Sprint 2/3:**

- Estender Cientifico com kwarg opcional `prescription_result` e priorizá-lo sobre `treatment_plan` na construção do query RAG.
- Manter `treatment_plan` como fallback para reports antigos (back-compat).

---

## Próximas revisões

Atualizar este doc quando:

- Qualquer dívida for fechada (mover seção pra "Histórico" no final).
- Novo gap arquitetural surgir em produção (ex.: condição comum repetidamente caindo no fallback).
- Sprint 2 estender `AnamnesisInput` (Dívida 4 vira a primeira a fechar).
