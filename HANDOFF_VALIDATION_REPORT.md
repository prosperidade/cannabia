# HANDOFF Validation Report — Série Sandbox Compliance Core (23–27)

## 1. Contexto

Em 2026-04-19, a série regulatória `docs/23` a `docs/27` foi integrada ao repositório, materializando o **Sandbox Compliance Core (SCC)** da CannabIA. Este relatório consolida a validação de coerência entre os novos documentos e o estado real do código-fonte.

Base de validação:

- Código-fonte em `src/` (Flask + PostgreSQL + SocketIO)
- Migrations em `migrations/` (`000`–`021` aplicadas)
- Documentação anterior em `docs/` (00–22)
- Histórico em `docs/progresso1.md` a `docs/progresso17_auditoria_completa_e_melhorias.md`
- Rotas implementadas em `src/web/routes/`
- Estrutura de agentes IA em `src/ai/agents/`

---

## 2. Operações de integração executadas

- Renomeação de arquivos para eliminar colisão no slot 22 (que já pertence a `22_EXECUTIVE_BACKLOG.md`):

  - `22_SANDBOX_COMPLIANCE_CORE.md` → `23_SANDBOX_COMPLIANCE_CORE.md`
  - `23_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md` → `24_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md`
  - `24_SCC_DATA_MODEL_AND_MIGRATIONS.md` → `25_SCC_DATA_MODEL_AND_MIGRATIONS.md`
  - `25_BLOCKCHAIN_ANCHORING_PROTOCOL.md` → `26_BLOCKCHAIN_ANCHORING_PROTOCOL.md`
  - `26_REGULATORY_TEMPLATES_LIBRARY.md` → `27_REGULATORY_TEMPLATES_LIBRARY.md`

- Atualização do título na linha 1 de cada arquivo renomeado.
- Atualização de todas as referências cruzadas internas entre os 5 documentos (22_SCC → 23_SCC).
- Ajuste da numeração de migrations do SCC de `018–030` para `024–036`, preservando `022` e `023` para os ajustes de integridade e padronização `TIMESTAMPTZ` previstos em `docs/progresso17_auditoria_completa_e_melhorias.md`.
- Atualização de `docs/13_MASTER_DOCUMENT_INDEX.md` com o novo bloco "Regulatório e Compliance (SCC)" e entradas individuais dos documentos 23–27.
- Atualização de `docs/05_WHITE_LABEL_AND_MONETIZATION_MODEL.md` com o plano Sandbox Ready, matriz ajustada e SKU de consultoria parceira.
- Atualização de `docs/10_SECURITY_COMPLIANCE_AND_AUDIT.md` com os invariantes arquiteturais do Art. 17 e a estratégia de imutabilidade em três camadas.
- Atualização de `docs/01_PRODUCT_AND_BUSINESS_FOUNDATION.md` (tabela de planos).
- Atualização de `docs/08_DATABASE_AND_DOMAIN_MODEL.md` com a extensão do SCC.
- Atualização de `docs/16_CURRENT_SYSTEM_INVENTORY.md` com o estado real em 2026-04-19.
- Atualização de `docs/22_EXECUTIVE_BACKLOG.md` com a Frente I (SCC e readiness ANVISA).
- Atualização de `docs/runbook.md` com a sequência real de migrations, os slots reservados e referência à série SCC.

---

## 3. Pontos onde os docs 23–27 estão coerentes com o código

### 3.1. Reaproveitamento de capacidades existentes (Seção 8.1 do doc 23)

Todas as capacidades reaproveitáveis declaradas no doc 23 foram confirmadas:

| Capacidade declarada | Confirmação no código |
|---|---|
| Multi-tenancy por `clinic_id`/`tenant_id` | `src/tenancy.py` com resolução por subdomínio, branding e integrações cifradas |
| Pipeline de IA com auditoria | `src/ai/clinical_flow.py` + `src/ai/service.py` + `src/repositories/ai_audit_repository.py` |
| Prontuário longitudinal | `src/repositories/medical_record_repository.py` + `src/repositories/patient_timeline_repository.py` |
| Telemetria pós-consulta | `scheduled_followups` + `iot_telemetry` + `src/services/telemetry_service.py` |
| RAG + base de conhecimento + PubMed | `src/knowledge/vector_store.py`, `src/knowledge/google_files.py`, `src/knowledge/legislation_catalog.py` |
| Prescrição determinística com Rules Engine e Safety Clamp | `src/ai/prescriber.py` + `src/ai/agents/prescritor.py` + `src/services/prescription_contract.py` |
| WhatsApp Business | `src/integrations/whatsapp.py` + `src/services/message_service.py` + `src/services/conversation_service.py` |
| Auditoria de IA | `src/repositories/ai_audit_repository.py` + tabela `ai_audit_logs` |

### 3.2. Agentes IA (doc 21 → SCC)

O `AgenteRegulatorio` (em `src/ai/agents/regulatorio.py`) já existe com skills `check_anvisa_compliance` e `query_legislation`. O SCC amplia esse agente com skills adicionais previstas para farmacovigilância e validação de invariantes do Art. 17.

O fluxo especialista-first em `src/ai/clinical_flow.py` (AgenteAnamnese → AgenteTratamento → AgenteCientifico) pode ser estendido com chain condicional "SCC-enabled" quando o tenant for do tipo associação com plano Sandbox Ready.

### 3.3. Rotas já implementadas

- `src/web/routes/knowledge.py` — blueprint `knowledge_bp` com prefixo `/api/v1/knowledge`, cobrindo catálogo, busca PubMed, classificação, monitores.
- `src/web/routes/regulatory.py` — blueprint `regulatory_bp` com prefixo `/api/v1/regulatory`, cobrindo upload, listagem e consulta estruturada de legislação via Google Files API.
- `src/web/routes/compliance.py` — blueprint `compliance_bp` com prefixo `/api/v1/org`, hospedando hoje um checklist ANVISA simples (5 checks com score).

---

## 4. Divergências e pontos de decisão

### 4.1. Migrations reservadas — divergência resolvida

**Divergência encontrada:** o doc original sugeria série `018–030` para as migrations do SCC. Essas posições já estavam ocupadas:

- `018_triage_links.sql` — emissão/uso de links de triagem (sprint 1)
- `019_conversations.sql` — threads de conversas (sprint 3)
- `020_tenant_extensions.sql` — branding/integrações/plano (sprint 6)
- `021_payment_requests_transactions.sql` — Pix EMV + conciliação (sprint 7)

Além disso, o `progresso17` reservou `022` e `023` para ajustes de integridade e padronização `TIMESTAMPTZ`.

**Resolução aplicada:** a série SCC foi renumerada para `024–036` em `docs/25_SCC_DATA_MODEL_AND_MIGRATIONS.md`. A decisão está refletida também em `docs/runbook.md`, `docs/08_DATABASE_AND_DOMAIN_MODEL.md` e `docs/22_EXECUTIVE_BACKLOG.md` (Frente I).

### 4.2. Blueprint `compliance.py` — decisão pendente

**Fato:** `src/web/routes/compliance.py` já existe como blueprint `compliance_bp` em `/api/v1/org`, com um checklist ANVISA simples de 5 checks derivados do estado real do banco.

**Decisão necessária:** o SCC tem escopo maior que esse blueprint atual. Há dois caminhos:

- **Opção A — Estender `compliance.py`.** Absorver os submódulos do SCC como grupos de endpoints adicionais. Vantagem: uma única superfície HTTP de compliance. Desvantagem: o arquivo fica muito grande.
- **Opção B — Blueprints dedicados por submódulo.** Criar `governance_bp`, `traceability_bp`, `pharmacovigilance_bp`, `sops_bp`, `evidence_bp`, `regulatory_reporting_bp`, `anchoring_bp`. Manter `compliance.py` como blueprint-resumo (o checklist permanece útil como dashboard). Vantagem: separação de responsabilidades, fácil de testar. Desvantagem: mais arquivos.

**Recomendação:** **opção B** é mais aderente ao padrão de blueprints do projeto (cada domínio claro tem seu arquivo). O `compliance.py` atual vira a fachada de dashboard agregador que consome os sete submódulos do SCC.

Essa decisão foi incorporada como item **I10** da Frente I no `docs/22_EXECUTIVE_BACKLOG.md`.

### 4.3. Divergência de terminologia — `tenants` × `clinics`

O SCC assume `tenants` como entidade-mãe com discriminador de tipo. A base de código ainda tem muitas tabelas transacionais indexadas por `clinic_id`. A migração está em curso (G1 no backlog executivo; progresso6/7/8).

**Recomendação:** a migration `024_tenants_evolution.sql` prevista no doc 25 deve **adicionar** `tenant_id` sem remover `clinic_id` e manter `clinics` como view ou coluna computada, conforme a Seção 2.1 do próprio doc 25 já prevê. Esse é exatamente o padrão adotado em `020_tenant_extensions.sql`, que evolui o modelo sem romper retrocompatibilidade.

### 4.4. Arquitetura de agentes — extensões pendentes

O `AgenteRegulatorio` precisa ganhar skills adicionais para ser útil no SCC:

- `validate_art17_invariants(entity, operation)` — valida que nenhuma tentativa de operação desliga rastreabilidade, farmacovigilância ou LGPD.
- `triage_adverse_event(report)` — classificação de severidade de evento adverso com IA.
- `check_sandbox_eligibility(association)` — validação automática de elegibilidade para o Edital.

Essas skills ainda não existem. Foram capturadas no backlog.

### 4.5. Webhooks externos SNGPC/VigiMed — ausentes

Nenhuma integração com SNGPC ou VigiMed/Notivisa existe hoje no repositório. Serão novas dependências externas do SCC, listadas no backlog como itens prioritários para a fase de produção de farmacovigilância.

### 4.6. Ancoragem em blockchain — ausente

Nenhum módulo de ancoragem existe hoje. Será criado conforme `docs/26_BLOCKCHAIN_ANCHORING_PROTOCOL.md`. O `docs/10_SECURITY_COMPLIANCE_AND_AUDIT.md` já posiciona a ancoragem como **extensão** (não substituição) da trilha de auditoria existente (`audit_trail` + `ai_audit_logs`).

---

## 5. Recomendações de primeiros passos de implementação

A ordem sugerida abaixo prioriza o que gera base sólida antes de avançar para o mais ambicioso. Detalhamento operacional em `docs/BACKLOG_SCC.md`.

### 5.1. Fechar base antes do SCC começar a escrever

1. **Migration `022`** — ajustes de integridade (UNIQUE, FK, CHECK, GIN em `ai_audit_logs`) — Prioridade 1 do `progresso17`. **Atualização 2026-04-19:** `migrations/022_integrity_hardening.sql` escrita, com 30 testes estáticos em `tests/test_migrations_integrity_hardening.py`. Pendente apenas aplicação em Postgres local — ver `docs/progresso18_integrity_hardening.md`.
2. **Migration `023`** — padronização `TIMESTAMP → TIMESTAMPTZ` — Prioridade 1 do `progresso17`. **Atualização 2026-04-19:** `migrations/023_timestamp_standardization.sql` escrita, idempotente via loop declarativo com guards em `information_schema`. Pendente apenas aplicação em Postgres local.
3. **CI/CD básico** — `.github/workflows/ci.yml` rodando `pytest -q` e `tsc --noEmit` em todo PR antes de qualquer merge do SCC.

### 5.2. Camada fundacional do SCC

4. **Migration `024_tenants_evolution.sql`** — evolução de `clinics` para `tenants` tipados (clinic, association, doctor), sem romper retrocompatibilidade.
5. **Blueprint `governance.py`** — Governance Hub com cadastro estatutário, RT, documentos institucionais.
6. **Validação automática de elegibilidade** — skill `check_sandbox_eligibility` no `AgenteRegulatorio`.

### 5.3. Rastreabilidade e imutabilidade

7. **Migrations `025` a `030`** — schemas de governance, members, quality, traceability (base + hash chaining + triggers).
8. **Blueprint `traceability.py`** com endpoints de registro e consulta de eventos imutáveis.
9. **Protocolo de ancoragem** — começar apenas pela camada 2 (hash chaining interno) antes de submeter provas à camada 3 (blockchain pública).

### 5.4. Farmacovigilância e reporting

10. **Migrations `031` a `033`** — pharmacovigilance, regulatory, crypto schemas.
11. **Integração VigiMed/Notivisa** — notificação automatizada de eventos adversos.
12. **Biblioteca de templates** — engine Jinja2 com os 5 planos obrigatórios + Dossiê de Elegibilidade.

### 5.5. Observabilidade e piloto

13. **Migrations `034` a `036`** — índices, views e seed data.
14. **Dashboard ANVISA-ready** — indicadores obrigatórios calculados em tempo real.
15. **Piloto-referência** — conforme `docs/24_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md`.

---

## 6. Pontos que exigem decisão humana antes de implementar

1. **Decisão 4.2 — blueprints do SCC.** Confirmação da opção B (blueprints dedicados por submódulo, com `compliance.py` como agregador).
2. **Modalidade comercial do plano Sandbox Ready.** Precificação concreta (fee + ticket por associado + setup) — fica para documento comercial separado.
3. **Associação-piloto.** Formalização da carta de intenção e do termo de participação.
4. **Rede de escritórios parceiros.** Critérios de credenciamento, modelo de comissionamento, contratos-base.
5. **Política formal de retenção de dados regulatórios.** Tempo de retenção pós-encerramento do sandbox, conforme Seção 11.3 do doc 23.
6. **Fornecedor de ancoragem em Polygon.** Smart contract dedicado ou serviço existente (ex.: Chainpoint, OriginStamp).
7. **Prioridade do SCC vs. backlog P1.** Confirmar se o bloco de integridade `022`–`023` é pré-requisito obrigatório (recomendado) ou pode correr em paralelo.

---

## 7. Conclusão

A integração da série SCC foi concluída estruturalmente. Os documentos 23–27 estão coerentes com o estado real do código após ajustes de numeração e cross-references. A plataforma já possui a base técnica necessária para iniciar a implementação: pipeline de IA operacional, multi-tenancy evoluído, auditoria de IA, agente regulatório, knowledge base híbrida, tenancy com integrações cifradas e campanhas ativas.

O SCC não é reescrita. É **extensão disciplinada** — camadas novas sobre capacidades que já existem, obedecendo aos invariantes do Art. 17 como regras arquiteturais imutáveis.

A próxima sessão deve abrir pelo item 5.1.1 acima — aplicar a migration `022` de integridade antes de qualquer escrita do SCC em tabelas append-only.

---

**Data:** 2026-04-19
**Base de código validada:** `src/` (snapshot pós-progresso17)
**Documentos validados:** `docs/23` a `docs/27`
**Próximo artefato:** `docs/BACKLOG_SCC.md`
