# AI Migration Backlog

**Status:** dívida explícita registrada na **Sprint 1 Track B.2**.
**Última atualização:** 2026-05-09.
**Owner:** indefinido — re-priorizar antes de junho/2026.

---

## 1. Migrar `gemini-1.5-flash` → `gemini-2.5-flash` (ou `-flash-lite`)

### Contexto

Hoje [src/ai/chains.py](src/ai/chains.py) usa `gemini-1.5-flash` em dois caminhos:

1. **Triage agent** — failover quando OpenAI circuit breaker abre ([chains.py:387](src/ai/chains.py#L387) `TRIAGE_MODEL_GEMINI = os.getenv("TRIAGE_MODEL_GEMINI", "gemini-1.5-flash")`).
2. **Scientific report (RAG path)** — caminho normal quando ChromaDB tem chunks ([chains.py:63](src/ai/chains.py#L63) `GEMINI_MODEL = "gemini-1.5-flash"`).

### Risco

- 🟡 **Pricing legacy:** `gemini-1.5-flash` não está mais em https://ai.google.dev/pricing (verificado 2026-05-09). Os valores hardcodados em [src/ai/pricing.py](src/ai/pricing.py) são os conhecidos da família 1.5 (input \$0.075/1M, output \$0.30/1M ≤128k contexto).
- 🔴 **Deprecation:** Google deprecated as famílias 1.5 e 2.0 ao longo de 2025/2026. Shutdown previsto para **junho/2026**. Calls a `gemini-1.5-flash` retornarão erro depois disso.

### Opções de substituição

| Modelo | Tier | Pricing input/output | Notas |
|---|---|---|---|
| `gemini-2.5-flash` | Flash | (verificar em ai.google.dev/pricing) | Substituto direto, capacidades semelhantes ao 1.5-flash |
| `gemini-2.5-flash-lite` | Lite | (verificar) | Mais barato, eventualmente menor qualidade — testar com fixture clínico |
| `gemini-2.5-pro` | Pro | mais caro | Reservar pra casos onde RAG tem contexto >128k |

### Plano

1. **Confirmar pricing real** — consultar ai.google.dev/pricing antes do código.
2. **Adicionar entry** ao `MODEL_PRICING` em [src/ai/pricing.py](src/ai/pricing.py) para o modelo escolhido.
3. **Trocar** `GEMINI_MODEL` em [chains.py:63](src/ai/chains.py#L63) e env var default `TRIAGE_MODEL_GEMINI` em [chains.py:387](src/ai/chains.py#L387).
4. **Smoke** — rodar 1 caso clínico fim-a-fim com RAG ativo, verificar que `tokens_per_stage["report"]["model"]` no audit log reflete o novo modelo.
5. **Rollback plan** — flag de feature `GEMINI_MODEL_VERSION` (env var) que permite rollback sem deploy se a qualidade clínica regredir.
6. **Manter 1.5-flash em `MODEL_PRICING`** por mais 1 sprint pra audit logs históricos não retornarem 0 ao serem reanalisados.

### Esforço estimado

- 1-2h de código (envs + pricing + smoke).
- 2-3h de validação clínica (rodar a base de casos quando o eval harness do Sprint 4 estiver pronto — antes disso, smoke manual com 5-10 casos).

### Gatilho

- 🔴 **Forçoso:** quando Google anunciar data definitiva de shutdown da família 1.5.
- 🟡 **Recomendado:** logo após o eval harness (Sprint 4) — facilita comparar qualidade old vs new com baseline objetiva.
- 🟢 **Mais cedo:** se algum caso real expor diferença de pricing significativa entre legacy e current.

### Critério de sucesso

- `MODEL_PRICING` tem o novo modelo + `gemini-1.5-flash` removido (ou movido pra seção "deprecated" mantida só pra audit retro).
- Nenhuma chamada produtiva usa `gemini-1.5-flash`.
- Audit logs novos têm o modelo correto em `model`.
- Suite de testes verde.
- Smoke ponta-a-ponta clínico sem regressão visível na qualidade do relatório.

---

## 2. Outras dívidas relacionadas (futuras)

- **Gateway central de LLM** ([Sprint 3 transformacional](../auditoria/RELATORIO_AGENTES_IA.md#81-gateway-central-de-llm-srcaillm_gatewaypy)) — quando ele existir, esta migração vira um patch único no gateway em vez de mudar `chains.py` + `pricing.py` + envs.
- **Provider abstraction** — adicionar suporte a Anthropic Claude / Mistral. Permite testar mesmo prompt em N providers e escolher por custo/qualidade. Junta bem com 1.

## 3. Histórico

- **2026-05-09 (Sprint 1 Track B.2):** dívida documentada após adicionar `gemini-1.5-flash` ao `MODEL_PRICING` para corrigir bug de cost mixing em [src/ai/service.py](src/ai/service.py). Decisão: não migrar agora, apenas registrar.
