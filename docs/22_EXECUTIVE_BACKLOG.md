# 22 — Backlog Executivo Consolidado

## 1. Propósito

Este documento consolida o backlog executivo ativo da CannabIA a partir do estado real observado no repositório em 2026-04-15.

Ele substitui a leitura isolada de backlogs históricos quando a pergunta é:

- o que já está resolvido
- o que está parcialmente resolvido
- quais são as próximas missões na ordem certa
- quais frentes exigem investimento técnico e operacional agora

---

## 2. Resumo executivo

### 2.1. O que já existe e pode ser reaproveitado

- fluxo clínico funcional com análise clínica, plano terapêutico e relatório científico
- camada de agentes com `BaseAgent`, `skills` próprias, memória via MemPalace e painel administrativo
- fluxo principal atualizado para execução por especialistas via `src/ai/clinical_flow.py`
- ambiente local de testes operacional com `pytest` instalado e suíte base verde
- setup local validado com migrations canônicas, seeds reais e normalização de `schema_migrations`
- arquitetura híbrida de conhecimento:
  - ChromaDB para artigos científicos chunkados
  - Google Files API para legislação e documentos grandes sem chunking
  - PostgreSQL como catálogo unificado (`knowledge_catalog`, `knowledge_monitors`)
- timeline do paciente, backfill inicial, detalhe do atendimento e base de prontuário longitudinal
- endpoints administrativos, clínicos e organizacionais conectados ao banco real

### 2.2. O que ainda impede maturidade operacional

- base regulatória ainda sem documentos reais em `data/legislation/`
- cobertura de testes ainda insuficiente para agentes, knowledge e regulatory, apesar da suíte base já estar operacional
- fluxo especialista-first ainda sem expansão para prescrição estruturada completa e compliance regulatória embutida no caminho principal
- dados demo e operação de knowledge/regulatory ainda superficiais para uso real
- integração por tenant ainda incompleta para credenciais, branding e integrações

---

## 3. Decisões arquiteturais ativas

### 3.1. Execução clínica

- o caminho principal passa a ser `specialists`, não `orchestrator-first`
- o orquestrador fica restrito a chains opcionais, testes administrativos e casos compostos
- o rollback operacional permanece disponível por `AI_EXECUTION_MODE=legacy`

### 3.2. Conhecimento

- artigos científicos permanecem em ChromaDB com embeddings Google
- legislação, resoluções e guidelines extensos permanecem em Google Files API com contexto completo
- o sistema não deve quebrar legislação em chunks quando a integridade semântica do documento for essencial

### 3.3. Memória

- MemPalace segue como camada fire-and-forget
- memória nunca bloqueia execução clínica
- PII continua proibido no palace; apenas padrões anonimizados e agregados

---

## 4. Backlog executivo por frente

### Frente A — Núcleo clínico especialista-first

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| A1 | Consolidar `SpecialistClinicalFlow` como caminho principal estável | Em andamento | Alta | Fluxo padrão previsível, sem acoplamento ao orquestrador |
| A2 | Expandir o fluxo principal para suportar triagem estruturada quando o canal de entrada exigir widgets | Planejado | Alta | Entrada clínica rica sem contaminar o fluxo mínimo |
| A3 | Integrar `AgentePrescritor` apenas em caminhos com dados estruturados suficientes (`weight_kg`, `height_cm`, histórico de uso) | Planejado | Alta | Prescrição segura sem gambiarras de preenchimento artificial |
| A4 | Integrar `AgenteRegulatorio` como etapa opcional e explícita após plano/prescrição | Planejado | Alta | Compliance acionável sem travar fluxos que ainda não têm documentação pronta |

**Arquivos-chave:**
- `src/ai/clinical_flow.py`
- `src/ai/service.py`
- `src/services/anamnesis_flow.py`
- `src/infra/tasks.py`
- `src/ai/agents/*.py`

### Frente B — Prescrição segura e dados clínicos estruturados

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| B1 | Definir fonte oficial para `weight_kg`, `height_cm` e `prior_cannabis_use` no fluxo clínico | Planejado | Alta | Contrato consistente para o `AgentePrescritor` |
| B2 | Adaptar intake/triagem/frontend para coletar os campos necessários de dosagem | Planejado | Alta | Entrada clínica compatível com dosagem segura |
| B3 | Criar gatilho explícito de “prescrição segura” separado do fluxo mínimo de anamnese | Planejado | Média | Menor acoplamento e menor risco clínico |

**Dependência crítica:** A2

### Frente C — Conhecimento científico e base regulatória

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| C1 | Popular `data/legislation/` com RDC 327, RDC 660, Lei 11.343 e normas CFM | Aberto | Alta | Regulatory utilizável em ambiente real |
| C2 | Executar upload validado para Google Files API e persistir catálogo | Aberto | Alta | Legislação pronta para consulta com contexto completo |
| C3 | Validar operação do `AgenteExtrator` para busca PubMed, classificação e ingestão | Parcial | Alta | Knowledge base operável de ponta a ponta |
| C4 | Ativar e validar monitores de conhecimento (`knowledge_monitors`) | Parcial | Média | Atualização contínua de fontes críticas |
| C5 | Expor melhor no frontend os fluxos de upload, query regulatória e monitores | Parcial | Média | Operação não dependente de chamadas manuais/API bruta |

**Arquivos-chave:**
- `src/knowledge/google_files.py`
- `src/ai/agents/extrator.py`
- `src/web/routes/knowledge.py`
- `src/web/routes/regulatory.py`
- `frontend/app/admin/knowledge/page.tsx`
- `data/legislation/`

### Frente D — Jornada longitudinal e prontuário

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| D1 | Fechar backlog de anexos/documentos no detalhe do atendimento | Aberto | Média | Prontuário operacional além do texto livre |
| D2 | Desenhar próxima migration do prontuário longitudinal | Aberto | Média | Evolução controlada do domínio clínico |
| D3 | Expandir estados do caso e eventos pós-consulta/follow-up | Parcial | Média | Timeline mais rica para operação e médico |

**Arquivos-chave:**
- `src/web/routes/atendimentos.py`
- `src/repositories/medical_record_repository.py`
- `src/repositories/patient_timeline_repository.py`
- `migrations/006_medical_records_foundation.sql`

### Frente E — Qualidade, testes e validação operacional

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| E1 | Instalar e padronizar execução de `pytest` no ambiente local | Concluído | Alta | Base de testes executável de forma previsível |
| E2 | Cobrir `SpecialistClinicalFlow`, guardrails e higiene de migrations com testes unitários | Em andamento | Alta | Segurança para refatoração incremental |
| E3 | Cobrir rotas `/knowledge`, `/regulatory` e `/admin/agents` | Em andamento | Alta | Menor risco nas superfícies novas |
| E4 | Rodar smoke tests dos fluxos tocados após cada bloco | Aberto | Alta | Redução de regressões silenciosas |
| E5 | Definir benchmark mínimo de custo/tempo para fluxo especialista vs legado | Aberto | Média | Decisão operacional baseada em dados |

**Observação:** em 2026-04-15 a suíte local alcançou `36` testes verdes, incluindo cobertura básica de `/admin/agents`.

### Frente F — Higiene de migrations, setup e seeds

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| F1 | Limpar definitivamente a trilha de migrations renomeadas (`012/013` antigas vs `013/014` novas) | Concluído | Alta | Histórico de banco sem ambiguidade |
| F2 | Validar `setup_local.py` com a sequência real de migrations e seeds | Concluído | Alta | Onboarding técnico confiável |
| F3 | Revisar dados de seed para knowledge/regulatory e fluxos administrativos | Aberto | Média | Ambiente demo mais próximo do produto |

**Observação:** em 2026-04-15 o runner passou a normalizar registros legados de `schema_migrations`, e `setup_local.py` foi validado ponta a ponta com PostgreSQL local.

### Frente G — Multi-tenancy, segurança e governança

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| G1 | Avançar a transição `clinic_id -> tenant_id` nas tabelas transacionais | Aberto | Alta | Base pronta para escala multi-tenant real |
| G2 | Completar integrações por tenant (WhatsApp, e-mail, IA, branding) | Aberto | Alta | Operação isolada por organização |
| G3 | Revisar CSRF, RBAC e superfícies novas de admin/knowledge | Parcial | Alta | Segurança coerente com a expansão do sistema |

### Frente H — Frontend operacional e adoção

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| H1 | Expor consulta regulatória e upload de legislação no frontend admin | Parcial | Média | Time não dependente de chamadas manuais |
| H2 | Expor monitores de conhecimento com gestão ativa/inativa e execução manual | Parcial | Média | Operação editorial de knowledge |
| H3 | Evoluir painel de agentes para inspeção de skills, diário e execução de testes dirigidos | Parcial | Média | Observabilidade administrativa da camada de agentes |

### Frente I — Sandbox Compliance Core (SCC) e readiness ANVISA

Frente aberta em 2026-04-19 materializando a série `docs/23` a `docs/27` e preparando a plataforma para o Sandbox Regulatório da ANVISA (RDC nº 1.014/2026). Ver `23_SANDBOX_COMPLIANCE_CORE.md` para o desenho completo do módulo transversal.

| ID | Missão | Status | Prioridade | Resultado executivo esperado |
|----|--------|--------|------------|------------------------------|
| I1 | Aplicar migrations de integridade pendentes em `022` (UNIQUE, FK, CHECK, GIN) e padronização `TIMESTAMPTZ` em `023` | SQL pronto, pendente aplicação | Alta | Base saneada antes do SCC começar a escrever tabelas append-only. Arquivos `migrations/022_integrity_hardening.sql` e `migrations/023_timestamp_standardization.sql` estão prontos e com 30 testes estáticos verdes — aplicação via `scripts/setup_local.py` fica para a próxima sessão no terminal |
| I2 | Escrever migrations `024`–`036` da série SCC conforme `25_SCC_DATA_MODEL_AND_MIGRATIONS.md` | Aberto | Alta | Schema físico do SCC materializado sem romper a trilha existente |
| I3 | Implementar Governance Hub (cadastro estatutário, RT, Matriz Técnico-Operacional, Dossiê de Elegibilidade) | Aberto | Alta | Associação operando com elegibilidade validada desde o onboarding |
| I4 | Implementar Seed-to-Patient Traceability com hash chaining append-only em PostgreSQL | Aberto | Alta | Rastreabilidade end-to-end auditável |
| I5 | Implementar Member-Patient Registry distinto do paciente genérico | Aberto | Alta | Associado regularmente cadastrado com vínculo validado antes de dispensação |
| I6 | Implementar Risk & Pharmacovigilance estruturado com captura por WhatsApp/web e notificação VigiMed/Notivisa | Aberto | Alta | Captura e notificação regulatória de eventos adversos em prazo legal |
| I7 | Implementar Regulatory Reporting & Audit Trail consolidado com geração dos 5 planos obrigatórios | Aberto | Alta | Parecer Final e Dossiê submissíveis gerados automaticamente |
| I8 | Implementar protocolo de ancoragem em blockchain pública conforme `26_BLOCKCHAIN_ANCHORING_PROTOCOL.md` | Aberto | Média | Prova independente e LGPD-conforme de integridade |
| I9 | Implementar engine de templates regulatórios conforme `27_REGULATORY_TEMPLATES_LIBRARY.md` | Aberto | Média | 90%+ de preenchimento automático nos documentos exigidos pelo Edital |
| I10 | Estender blueprint `src/web/routes/compliance.py` existente para hospedar endpoints dos submódulos SCC ou criar blueprints dedicados | Aberto | Média | Superfície HTTP coerente com o módulo |
| I11 | Piloto-referência com associação parceira conforme `24_PILOT_PROGRAM_AND_INSTITUTIONAL_PARTNERSHIPS.md` | Planejado | Alta | Caso de referência documentado e auditável |
| I12 | Aproximação institucional com entidade nacional representativa | Planejado | Média | Modelo de credenciamento ou recomendação setorial |

**Arquivos-chave previstos:**
- `migrations/024_tenants_evolution.sql` em diante
- `src/web/routes/compliance.py` (existente, candidato a estender)
- `src/web/routes/knowledge.py`, `regulatory.py` (integração com SCC)
- `src/services/` — novos serviços por submódulo do SCC
- `data/templates/` — biblioteca de templates regulatórios

**Dependências externas:**
- Publicação do Edital de Chamamento Público da ANVISA (parametriza campos e checklists)
- Integração com SNGPC (quando aplicável)
- Integração com VigiMed/Notivisa para farmacovigilância
- OpenTimestamps e Polygon para ancoragem

---

## 5. Ordem recomendada de execução

1. Fechar Frente C1/C2 para tornar a base regulatória realmente utilizável.
2. Avançar Frente E3/E4 e F3 para cobrir superfícies novas e enriquecer o ambiente demo.
3. Fechar Frente A1 e documentar benchmark inicial contra o legado.
4. Executar Frente B1/B2 para preparar integração segura do `AgentePrescritor`.
5. Fechar Frente C3/C4/H1/H2 para operar conhecimento e legislação como produto.
6. Avançar Frente D1/D2/D3 para aprofundar a jornada longitudinal.
7. Atacar Frente G1/G2/G3 como eixo estrutural de escala.

---

## 6. Próximas três missões recomendadas

### Missão 1 — Base regulatória real

- inserir documentos reais em `data/legislation/`
- subir os arquivos para Google Files API
- validar `/api/v1/regulatory/query` com fontes reais

### Missão 2 — Cobertura das superfícies novas

- expandir testes de `/knowledge` e `/regulatory`
- aprofundar a cobertura recém-criada de `/admin/agents`
- validar fluxos administrativos e regulatory sem depender apenas de teste manual

### Missão 3 — Contrato clínico para prescrição segura

- definir fonte oficial para `weight_kg`, `height_cm` e `prior_cannabis_use`
- adaptar intake/triagem para coletar os campos mínimos
- preparar a entrada controlada do `AgentePrescritor` fora do fluxo mínimo

---

## 7. Critério de avanço para a próxima fase

Considera-se a base pronta para avançar de forma segura quando:

- o fluxo especialista estiver estável e testado
- a base regulatória estiver carregada e consultável
- a trilha de migrations estiver saneada
- a suíte mínima de testes estiver operacional
- houver contrato claro para entrada do `AgentePrescritor`

---

## 8. Conclusão

O sistema já saiu da fase de fundação e entrou em uma fase de consolidação arquitetural. O backlog correto agora não é “criar tudo”, e sim:

- estabilizar o que já existe
- conectar corretamente as frentes já abertas
- operacionalizar conhecimento e regulação
- preparar a entrada segura da prescrição avançada e da escala multi-tenant
