# Progresso 1

## Data

2026-04-01

## Objetivo do dia

Iniciar a organização formal da documentação operacional da CannabIA e consolidar a primeira frente de planejamento de execução.

## Trabalho realizado

- Leitura integral da documentação nova em `docs/00` até `docs/14`
- Comparação entre a documentação consolidada e o estado atual do sistema
- Identificação dos principais gaps entre produto documentado e implementação real
- Definição da primeira fase de correções e organização da base
- Criação do backlog executável da sprint em `docs/15_SPRINT_1_EXECUTION_BACKLOG.md`
- Criação do padrão de diário operacional com este arquivo e com `docs/runbook.md`
- Atualização do `README.md` para aderência com a plataforma documentada
- Criação do inventário técnico oficial do sistema em `docs/16_CURRENT_SYSTEM_INVENTORY.md`
- Correção do painel de métricas de IA para refletir os dados reais auditados
- Limpeza da migration `002_whatsapp_sessions.sql`
- Melhoria do runner de migrations para execução sequencial local
- Ajuste da integração de e-mail para usar a configuração central do projeto
- Normalização incremental de permissões considerando papel global e papel contextual
- Criação da foundation migration de tenancy em `migrations/004_tenants_foundation.sql`
- Criação do repositório inicial de tenant e do plano de transição em `docs/17_TENANT_MIGRATION_PLAN.md`
- Criação da foundation de timeline do paciente em `migrations/005_patient_timeline_foundation.sql`
- Integração de eventos de jornada em anamnese, revisão clínica e agendamento
- Exposição inicial da timeline longitudinal na tela de detalhe de atendimento
- Criação do backlog da sprint 2 em `docs/18_SPRINT_2_BACKLOG.md`
- Criação da foundation mínima de prontuário longitudinal em `migrations/006_medical_records_foundation.sql`
- Inclusão de registro clínico do médico no detalhe do atendimento com persistência em prontuário
- Integração do prontuário com timeline para registrar conduta e atualização clínica
- Formalização da estratégia oficial de frontend em `docs/19_FRONTEND_STRATEGY.md`
- Definição arquitetural de migração futura do frontend para Next.js
- Criação do contrato inicial de API para o novo frontend em `docs/20_FRONTEND_API_CONTRACT.md`
- Implementação da primeira leva de endpoints JSON em `/api/v1` para sessão, contexto, atendimentos, timeline, prontuário, dashboard e agendamentos
- Bootstrap inicial do `frontend/` em Next.js com login, shell autenticado, lista de atendimentos e detalhe clínico
- Ajuste do backend para expor CORS controlado por `FRONTEND_ORIGIN` durante a transição para o frontend novo
- Correção do bootstrap TypeScript do frontend para remover inconsistências de tipagem React
- Criação das páginas reais de `dashboard` e `agendamentos` no Next.js consumindo a API v1

## Decisões registradas

- A CannabIA não deve ser reconstruída do zero
- A evolução seguirá por adaptação incremental da base atual
- O foco inicial será consolidação da base, quick wins técnicos e preparação da generalização de tenancy
- A partir de 2026-04-01, o time passa a registrar progresso diário em arquivos `progressoN.md`

## Principais pontos observados

- O sistema atual já possui boa base em Flask, multi-tenancy por `clinic_id`, pipeline de IA, webhook WhatsApp e auditoria
- A documentação nova já está à frente da implementação em tenancy amplo, white-label, jornadas completas, prontuário longitudinal, acompanhamento, billing e pagamentos
- Há inconsistências imediatas a corrigir em documentação, métricas de IA, setup de migrations e semântica de papéis
- A timeline do paciente deixou de ser inexistente e passa a existir em foundation mínima, ainda sem prontuário longitudinal completo
- Os formulários já tinham uso inconsistente de CSRF entre templates e backend; a validação foi compatibilizada para não quebrar o legado
- O prontuário longitudinal deixou de ser inexistente e passa a ter entidade agregadora com entradas clínicas e importação inicial da anamnese
- A direção oficial de frontend deixa de ser Jinja/Flask e passa a ser uma migração gradual para Next.js, preservando Flask como backend
- O backend passa a precisar de uma camada API mais explícita para servir o frontend externo sem depender de templates HTML
- A transição para Next.js já pode começar apoiada em endpoints reais, sem bloquear a convivência com o frontend legado
- O frontend novo já tem fundação prática no repositório, mesmo antes de substituir o legado em produção
- O frontend novo já cobre overview operacional, agenda e atendimento em rotas separadas

## Próximos passos

- Executar o backlog da sprint 1
- Validar a aplicação das migrations em ambiente local
- Revisar os pontos remanescentes de permissões por contexto
- Expandir a timeline para acompanhamento, alertas e próximos estados clínicos
- Evoluir o prontuário para anexos, exames, consultas formais e trilha de auditoria clínica
- Preparar contratos de API e bootstrap do futuro frontend em Next.js
- Implementar a primeira leva de endpoints JSON para sessão, atendimentos, timeline, prontuário e agendamento
- Evoluir autenticação e contratos da API para consumo do frontend Next.js
- Conectar o frontend Next.js ao restante das APIs e expandir dashboard, agendamento e auditoria de IA
- Validar build local do frontend e ampliar a cobertura para mensagens e auditoria de IA

## Arquivos relevantes do dia

- `docs/15_SPRINT_1_EXECUTION_BACKLOG.md`
- `docs/16_CURRENT_SYSTEM_INVENTORY.md`
- `docs/17_TENANT_MIGRATION_PLAN.md`
- `docs/18_SPRINT_2_BACKLOG.md`
- `docs/progresso1.md`
- `docs/runbook.md`
- `README.md`
- `migrations/004_tenants_foundation.sql`
- `migrations/005_patient_timeline_foundation.sql`
- `migrations/006_medical_records_foundation.sql`
- `docs/19_FRONTEND_STRATEGY.md`
- `docs/20_FRONTEND_API_CONTRACT.md`

## Bloqueios

- Nenhum bloqueio formal registrado neste início de ciclo

## Observação de uso

O próximo dia de trabalho deve abrir `docs/progresso2.md`, mantendo a mesma estrutura base e registrando a data real da nova sessão.
