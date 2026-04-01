# 15 — Backlog de Execução da Sprint 1

## 1. Propósito do documento

Este documento transforma a análise comparativa entre a documentação consolidada da CannabIA e o sistema atualmente implementado em um **backlog executável de sprint**, com foco na primeira fase de correções, organização e preparação da base.

Ele não substitui o roadmap macro já aprovado. Seu papel é operacionalizar o início da execução com:

- épicos claros
- tarefas técnicas objetivas
- dependências
- ordem sugerida de execução por arquivo
- critérios de pronto da sprint

---

## 2. Objetivo da sprint

Executar uma sprint de **consolidação da base atual**, cobrindo três frentes:

1. Alinhar o repositório real com a documentação nova
2. Corrigir inconsistências técnicas já identificadas na base existente
3. Preparar o terreno para a generalização de `clinic_id` para `tenant_id` sem ruptura prematura

---

## 3. Escopo confirmado da sprint

Esta sprint cobre:

- Inventário técnico do sistema atual
- Alinhamento documental mínimo do repositório
- Correções de consistência em autenticação, autorização, métricas e setup
- Limpeza de acoplamentos óbvios que dificultam a próxima fase
- Fundação inicial da camada de tenancy ampliada

---

## 4. Fora de escopo

Esta sprint **não** deve tentar concluir:

- White-label completo por tenant
- Pagamentos e QR Code
- Billing recorrente
- Prontuário longitudinal completo
- Módulo de acompanhamento semanal completo
- Integração PubMed
- Migração total de todas as tabelas para `tenant_id`

Esses itens permanecem dependentes das fases seguintes do roadmap principal.

---

## 5. Resultado esperado ao fim da sprint

Ao final da sprint, a CannabIA deve sair com:

- Repositório documentalmente coerente com a visão atual
- Mapa claro de módulos, tabelas, rotas e fluxos existentes
- Quick wins técnicos aplicados na base atual
- Inconsistências centrais de métricas, permissões e setup reduzidas
- Base aditiva criada para iniciar a evolução de tenancy
- Plano de migração imediata para a próxima sprint

---

## 6. Resumo executivo dos épicos

| Épico | Foco | Prioridade | Resultado principal |
|------|------|------------|---------------------|
| **A** | Alinhamento documental e inventário | Muito alta | Repositório passa a refletir a nova plataforma |
| **B** | Correções técnicas de coerência da base | Muito alta | Quick wins e remoção de inconsistências atuais |
| **C** | Fundação da generalização de tenancy | Alta | Estrutura inicial para `tenant` sem quebrar o sistema |
| **D** | Preparação da próxima sprint | Alta | Backlog seguinte pronto com dependências claras |

---

## 7. Backlog detalhado por épico

### Épico A — Alinhamento documental e inventário

**Objetivo:** fazer a documentação local refletir o estado atual do produto e gerar um inventário técnico operacional do sistema real.

| ID | Tarefa | Arquivos principais | Tipo | Prioridade |
|----|--------|---------------------|------|------------|
| **A1** | Atualizar `README.md` para remover a visão antiga de "sistema clínico para múltiplas clínicas" e alinhar com a plataforma white-label multi-tenant documentada | `README.md` | Correção documental | Muito alta |
| **A2** | Corrigir referências documentais antigas que ainda apontam para arquivos removidos ou obsoletos | `README.md` | Correção documental | Muito alta |
| **A3** | Produzir inventário oficial do sistema atual com módulos, rotas, tabelas, integrações e aderência por domínio | `docs/16_CURRENT_SYSTEM_INVENTORY.md` | Novo documento | Muito alta |
| **A4** | Registrar matriz `reaproveitar / adaptar / expandir / criar` com vínculo direto aos arquivos atuais | `docs/16_CURRENT_SYSTEM_INVENTORY.md` | Novo documento | Alta |

**Critério de pronto do épico:**

- qualquer pessoa nova no projeto consegue ler o `README` e entender a plataforma atual sem cair na documentação antiga
- existe um documento de inventário técnico servindo como ponte entre código e roadmap

---

### Épico B — Correções técnicas de coerência da base

**Objetivo:** resolver inconsistências já existentes no sistema e reduzir dívida imediata antes de mexer em tenancy estrutural.

| ID | Tarefa | Arquivos principais | Tipo | Prioridade |
|----|--------|---------------------|------|------------|
| **B1** | Corrigir incompatibilidade entre a rota de métricas de IA, o repositório e o template | `src/web/routes/ai_admin.py`, `src/repositories/ai_audit_repository.py`, `src/templates/ai_metrics.html` | Correção funcional | Muito alta |
| **B2** | Revisar o modelo atual de papéis para reduzir conflito entre `users.role`, `user_clinics.role` e verificações em rota | `src/app.py`, `src/infra/security.py`, `src/repositories/user_repository.py`, `src/repositories/tenancy_repository.py` | Correção estrutural leve | Muito alta |
| **B3** | Corrigir a migration de sessão WhatsApp, removendo placeholder inseguro e deixando o setup reproduzível | `migrations/002_whatsapp_sessions.sql`, `src/infra/run_migrations.py` | Correção de infraestrutura | Muito alta |
| **B4** | Revisar setup inicial e bootstrap de banco/documentação de migração para não depender de instruções obsoletas | `README.md`, `src/infra/run_migrations.py`, `migrations/001_initial_schema.sql` | Correção operacional | Alta |
| **B5** | Ajustar integração de e-mail para usar de fato as configurações centralizadas já existentes | `src/integrations/email.py`, `src/config.py` | Correção técnica | Alta |
| **B6** | Revisar proteção de rotas administrativas para garantir coerência com os papéis hoje suportados pela aplicação | `src/web/routes/dashboard.py`, `src/web/routes/atendimentos.py`, `src/web/routes/historico_atendimento.py`, `src/web/routes/scheduling_chain.py`, `src/web/routes/realtime_notifications.py` | Correção de autorização | Alta |

**Critério de pronto do épico:**

- painel de IA deixa de depender de chaves inexistentes
- setup local e migrations ficam claros e reproduzíveis
- semântica de papéis fica explícita o suficiente para sustentar a próxima fase

---

### Épico C — Fundação da generalização de tenancy

**Objetivo:** preparar a estrutura inicial de `tenant` como camada aditiva, preservando a operação atual baseada em `clinic_id`.

| ID | Tarefa | Arquivos principais | Tipo | Prioridade |
|----|--------|---------------------|------|------------|
| **C1** | Definir migration inicial de tenancy com `tenants`, `tenant_types`, vínculo entre `clinics` e `tenants`, e base para branding/integrações | `migrations/004_tenants_foundation.sql` | Nova migration | Alta |
| **C2** | Criar repositório inicial de tenancy ampliada | `src/repositories/tenant_repository.py` | Novo componente | Alta |
| **C3** | Adaptar a resolução de contexto para introduzir `g.tenant_id` e manter `g.clinic_id` como compatibilidade temporária | `src/tenancy.py`, `src/app.py` | Refatoração controlada | Alta |
| **C4** | Preparar a evolução de `user_clinics` para `user_tenant_roles` sem quebrar login e sessão atuais | `src/repositories/tenancy_repository.py`, `migrations/004_tenants_foundation.sql` | Refatoração controlada | Alta |
| **C5** | Criar documento técnico curto da estratégia de transição `clinic_id -> tenant_id` | `docs/17_TENANT_MIGRATION_PLAN.md` | Novo documento | Alta |

**Critério de pronto do épico:**

- a base já reconhece formalmente o conceito de tenant
- o sistema continua rodando com a semântica atual de clínica
- existe plano claro para as próximas migrações de domínio

---

### Épico D — Preparação da próxima sprint

**Objetivo:** fechar a sprint com backlog imediatamente acionável para jornadas, prontuário e acompanhamento.

| ID | Tarefa | Arquivos principais | Tipo | Prioridade |
|----|--------|---------------------|------|------------|
| **D1** | Quebrar as próximas frentes em stories técnicas para jornada do paciente, jornada do médico e timeline | `docs/18_SPRINT_2_BACKLOG.md` | Novo documento | Alta |
| **D2** | Registrar dependências entre tenancy, jornadas, prontuário e acompanhamento | `docs/18_SPRINT_2_BACKLOG.md` | Novo documento | Alta |
| **D3** | Definir critérios de entrada da sprint seguinte | `docs/18_SPRINT_2_BACKLOG.md` | Novo documento | Média |

**Critério de pronto do épico:**

- a sprint 2 pode começar sem nova rodada extensa de descoberta

---

## 8. Ordem sugerida de execução por arquivo

### Bloco 1 — Correção documental e inventário

1. `README.md`
   Atualizar posicionamento do produto, arquitetura documental e links de documentação.
2. `docs/16_CURRENT_SYSTEM_INVENTORY.md`
   Criar inventário técnico oficial do sistema atual.

### Bloco 2 — Quick wins técnicos

3. `src/repositories/ai_audit_repository.py`
   Ajustar retorno do resumo para o contrato real consumido na camada web.
4. `src/web/routes/ai_admin.py`
   Alinhar nomes de métricas, autorização e payload enviado ao template.
5. `src/templates/ai_metrics.html`
   Substituir placeholder por painel simples aderente aos dados disponíveis.
6. `src/integrations/email.py`
   Passar a usar `SMTP_SERVER` e `SMTP_PORT` de configuração central.
7. `migrations/002_whatsapp_sessions.sql`
   Remover placeholder inconsistente e deixar a migration limpa.
8. `src/infra/run_migrations.py`
   Garantir execução previsível das migrations já existentes.

### Bloco 3 — Ajuste de semântica de acesso

9. `src/infra/security.py`
   Revisar a estratégia atual de `role_required`.
10. `src/repositories/user_repository.py`
    Deixar claro o papel global do usuário autenticado.
11. `src/repositories/tenancy_repository.py`
    Preparar retorno de contexto compatível com tenant futuro.
12. `src/app.py`
    Ajustar carregamento de usuário e contexto para reduzir ambiguidade.
13. `src/tenancy.py`
    Introduzir base de `tenant_id` com compatibilidade transitória.

### Bloco 4 — Fundação de tenancy

14. `migrations/004_tenants_foundation.sql`
    Criar base aditiva para tenants, tipos, branding e integrações.
15. `src/repositories/tenant_repository.py`
    Criar acesso inicial aos novos registros de tenancy.
16. `docs/17_TENANT_MIGRATION_PLAN.md`
    Registrar a estratégia de transição.

### Bloco 5 — Fechamento da sprint

17. `docs/18_SPRINT_2_BACKLOG.md`
    Criar backlog da sprint seguinte com base no que sair desta sprint.

---

## 9. Dependências práticas

| Item | Depende de |
|------|------------|
| Correção do painel de IA | Nenhuma |
| Limpeza de migrations | Nenhuma |
| Revisão de roles/permissões | Leitura do comportamento atual |
| Introdução de `tenant_id` no contexto | Revisão de `tenancy.py` e `tenancy_repository.py` |
| Migration de tenants | Definição mínima de nomenclatura e compatibilidade |
| Backlog da sprint 2 | Fechamento dos épicos A, B e C |

---

## 10. Priorização sugerida por sequência de dias

| Dia | Foco |
|-----|------|
| **Dia 1** | Épico A completo + início do B1 |
| **Dia 2** | Fechar B1, B3 e B4 |
| **Dia 3** | B2, B5 e B6 |
| **Dia 4** | C1 e C2 |
| **Dia 5** | C3, C4 e C5 |
| **Dia 6** | D1, D2 e D3 + revisão final |

---

## 11. Riscos da sprint

| Risco | Impacto | Mitigação |
|------|---------|-----------|
| Mudar semântica de papéis cedo demais | Pode quebrar acesso atual | Fazer ajuste incremental e compatível |
| Introduzir `tenant_id` de forma invasiva | Pode espalhar refatoração prematura | Limitar esta sprint à fundação e compatibilidade |
| Corrigir migrations sem validar ordem de execução | Pode piorar setup local | Revisar bootstrap junto com `run_migrations.py` |
| Tentar já modelar jornadas completas | Estoura escopo | Manter foco em base e preparação |

---

## 12. Critérios de pronto da sprint

- `README.md` aderente à plataforma documentada
- Inventário técnico oficial criado
- Painel de IA coerente com os dados retornados pelo backend
- Migration `002` limpa e setup local menos frágil
- Estratégia atual de papéis documentada e tecnicamente menos ambígua
- Migration inicial de tenancy criada
- Contexto de request preparado para suportar `tenant_id` sem quebrar `clinic_id`
- Plano de migração de tenancy documentado
- Backlog da sprint seguinte criado

---

## 13. Recomendação final de execução

Esta sprint deve ser tratada como sprint de **arrumação estrutural com entrega útil**, não como sprint de expansão funcional pesada.

O melhor uso dela é:

1. eliminar inconsistências óbvias já existentes
2. alinhar documentação e código
3. criar fundação de tenancy ampla
4. sair pronto para atacar jornadas, prontuário e acompanhamento na sprint seguinte

---

## 14. Conclusão

O backlog desta sprint respeita a direção já aprovada para a CannabIA:

- preservar a base atual
- adaptar antes de reconstruir
- corrigir o que hoje está inconsistente
- estruturar tenancy antes de ampliar módulos centrais

Com isso, a próxima fase deixa de ser uma exploração difusa e passa a ser uma execução técnica disciplinada.
