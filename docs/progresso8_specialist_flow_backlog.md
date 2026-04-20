# Progresso 8 — Fluxo Especialista-First + Backlog Executivo

## Data
2026-04-15

## Objetivo do dia
1. Confirmar a direção arquitetural de agentes independentes com `skills` próprias
2. Remover o orquestrador do caminho crítico do fluxo clínico principal
3. Consolidar um backlog executivo coerente com o estado real do sistema
4. Atualizar a documentação operacional pertinente

## Trabalho realizado

### 1. Fluxo clínico especialista-first

- Criado `src/ai/clinical_flow.py` como fachada explícita de execução clínica
- Definido `SpecialistClinicalFlow` como caminho padrão com sequência:
  - `AgenteAnamnese`
  - `AgenteTratamento`
  - `AgenteCientifico`
- Mantido rollback operacional por `AI_EXECUTION_MODE=legacy`

### 2. Separação de responsabilidades por especialista

- Criado `src/ai/agents/tratamento.py`
- O objetivo foi evitar empurrar para o `AgentePrescritor` um payload incompleto de dosagem
- O `AgenteTratamento` encapsula apenas o plano terapêutico atual
- O `AgentePrescritor` fica reservado para fluxos com dados clínicos estruturados suficientes

### 3. Integração do novo fluxo nos pontos reais de entrada

- `src/ai/service.py` passou a usar `build_clinical_flow()`
- `src/services/anamnesis_flow.py` passou a usar o fluxo especialista-first
- `src/infra/tasks.py` passou a usar o mesmo caminho
- A resposta final foi mantida compatível com o payload legado (`clinical_analysis`, `treatment_plan`, `scientific_report`, `token_usage`)

### 4. Superfície administrativa atualizada

- `src/web/routes/admin_agents.py` atualizado para listar e inspecionar `AgenteTratamento`
- `frontend/app/admin/agentes/page.tsx` atualizado para reconhecer o novo agente

### 5. Validação técnica

- Criado `tests/test_clinical_flow.py` com cobertura básica do fluxo especialista
- Executado `python -m py_compile` nos arquivos Python alterados com sucesso
- Não foi possível rodar `pytest` porque o ambiente local observado não possui o módulo instalado

### 6. Documentação consolidada

- Criado `docs/22_EXECUTIVE_BACKLOG.md`
- Atualizados:
  - `docs/13_MASTER_DOCUMENT_INDEX.md`
  - `docs/16_CURRENT_SYSTEM_INVENTORY.md`
  - `docs/18_SPRINT_2_BACKLOG.md`
  - `docs/21_AGENT_ARCHITECTURE.md`

## Decisões registradas

1. O orquestrador deixa de ser o caminho principal do sistema.
2. Cada agente deve manter suas `skills` e sua especialidade local.
3. O fluxo clínico padrão passa a ser composto por especialistas conectados por uma fachada fina.
4. O `AgentePrescritor` só entra quando houver contrato de entrada suficiente para dosagem segura.
5. A arquitetura de conhecimento permanece híbrida:
   - ChromaDB para artigos chunkados
   - Google Files API para legislação e documentos grandes sem chunking

## Próximos passos

1. Instalar `pytest` e fechar a base mínima de testes
2. Sanear a trilha de migrations antigas vs renomeadas
3. Popular `data/legislation/` com documentos reais e validar o regulatory end-to-end
4. Preparar a entrada estruturada para futura integração do `AgentePrescritor`

## Arquivos relevantes do dia

### Criados

- `src/ai/agents/tratamento.py`
- `src/ai/clinical_flow.py`
- `tests/test_clinical_flow.py`
- `docs/22_EXECUTIVE_BACKLOG.md`
- `docs/progresso8_specialist_flow_backlog.md`

### Modificados

- `src/ai/agents/__init__.py`
- `src/ai/service.py`
- `src/services/anamnesis_flow.py`
- `src/infra/tasks.py`
- `src/web/routes/admin_agents.py`
- `frontend/app/admin/agentes/page.tsx`
- `.env.example`
- `docs/13_MASTER_DOCUMENT_INDEX.md`
- `docs/16_CURRENT_SYSTEM_INVENTORY.md`
- `docs/18_SPRINT_2_BACKLOG.md`
- `docs/21_AGENT_ARCHITECTURE.md`

## Bloqueios

- `pytest` não está disponível no ambiente local atual
- `data/legislation/` ainda não possui os documentos regulatórios reais
- Persistem pendências no versionamento de migrations renomeadas

## Primeira missão sugerida para a próxima sessão

Instalar o ambiente de testes, rodar `pytest`, corrigir a trilha básica e então sanear as migrations antigas vs renomeadas antes de avançar para regulatory com dados reais.
