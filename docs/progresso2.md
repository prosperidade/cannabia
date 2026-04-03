# Progresso 2

## Data

2026-04-02

## Objetivo do dia

Validar o runtime real do novo frontend em Next.js e iniciar a próxima expansão funcional após o fluxo clínico principal.

## Trabalho realizado

- Leitura do diário anterior para confirmar a primeira missão do dia
- Verificação do estado atual do `frontend/` e dos pré-requisitos locais de Node.js e npm
- Execução de `npm install` no `frontend/` com geração de `package-lock.json`
- Validação de `npm run build` do Next.js com sucesso
- Subida local do backend Flask usando o virtualenv do projeto em `env\Scripts\python.exe`
- Verificação da API local em `http://127.0.0.1:5000/api/v1/session/me` com resposta `200`
- Subida local do frontend Next.js em `http://127.0.0.1:3001`
- Smoke test HTTP das rotas `/login`, `/dashboard`, `/atendimentos`, `/mensagens` e `/auditoria-ia`
- Implementação da página `Mensagens` no frontend novo consumindo `GET /api/v1/messages`
- Implementação da página `Auditoria IA` no frontend novo consumindo `GET /api/v1/admin/ai-metrics`
- Expansão da navegação do `AppShell` para incluir mensagens e auditoria
- Ampliação do cliente de API e dos tipos TypeScript para suportar as novas superfícies
- Nova validação de `npm run build` após a expansão do frontend, novamente sem falhas
- Diagnóstico do ambiente local de banco e identificação de `DATABASE_URL` apontando para um banco inexistente
- Verificação de que o banco `enjoyfun` local não pertence à CannabIA e não deveria ser reutilizado
- Criação do banco local `cannabia`
- Correção do runner de migrations em `src/infra/run_migrations.py` para executar arquivos SQL completos sem quebrar em blocos vazios
- Aplicação das 6 migrations no banco local recém-criado
- Execução de `fix_admin.py` para garantir o usuário `admin` e o vínculo em `user_clinics`
- Validação de login real pela API com `admin/admin123`
- Validação autenticada das rotas `/api/v1/dashboard`, `/api/v1/messages` e `/api/v1/admin/ai-metrics`
- Verificação de CORS e cookie de sessão para `http://localhost:3000`
- Refinamento da página `Mensagens` com paginação real baseada no `meta` da API
- Enriquecimento da página `Auditoria IA` com taxas derivadas de sucesso, erro e bloqueio
- Correção do hash bcrypt inválido do `admin` na migration inicial `migrations/001_initial_schema.sql`
- Correção do `render.yaml` para usar Blueprint válido com banco PostgreSQL gerenciado no Render
- Implementação de filtros remotos reais para mensagens no backend (`sender`, `search`) e catálogo de contatos
- Implementação de cortes operacionais remotos para auditoria de IA (`status`, `days`, `limit`)
- Criação do script idempotente `scripts/seed_local_demo.py` para popular ambiente local
- Execução do seed local com dados mínimos de pacientes, mensagens, agendamentos, relatórios e logs de IA
- Validação pós-seed dos totais do dashboard (`8` mensagens, `3` pacientes, `3` agendamentos, `4` logs de IA)
- Migração do frontend local para `3001` para evitar conflito com outro projeto na `3000`
- Implementação de proxy same-origin em `frontend/app/api/v1/[...path]/route.ts` para o frontend falar com o backend sem depender de CORS no navegador
- Inclusão do serviço `cannabia-frontend` no `render.yaml` para deploy completo de frontend + backend + banco no Render

## Decisões registradas

- A missão prioritária da manhã foi considerada concluída após install, build e smoke test do frontend novo
- A próxima expansão do Next.js deve seguir usando endpoints já existentes do backend, sem criar contrato novo desnecessariamente
- As novas áreas do frontend foram abertas com rotas limpas em Next.js, mantendo o backend Flask como fonte de domínio e autenticação
- O setup local da CannabIA deve usar banco PostgreSQL próprio; não é aceitável redirecionar o projeto para um banco de outro sistema só para contornar bootstrap
- O bootstrap mínimo local passa a depender de migrations funcionais e de um seed de `admin` realmente utilizável
- O fluxo de nuvem deve seguir por PostgreSQL gerenciado no Render com blueprint válido, evitando o bloco incorreto anterior que modelava banco como serviço privado comum
- O seed local passa a ser parte prática da validação do frontend novo sempre que o banco estiver vazio
- O frontend local não deve mais disputar a `3000`; a porta padrão operacional passa a ser `3001`
- O deploy de nuvem passa a contemplar dois serviços web no blueprint: API Flask e frontend Next.js

## Próximos passos

- Validar o fluxo visual completo no navegador com login manual no frontend novo já conectado ao backend local
- Configurar e aplicar o novo banco PostgreSQL gerenciado no Render usando o blueprint corrigido
- Aplicar o blueprint no Render a partir do repositório para criar automaticamente API, frontend e banco
- Ligar os segredos de backend no ambiente de nuvem antes do próximo deploy
- Evoluir a página de mensagens com paginação remota mais densa e, se necessário, filtros salvos
- Enriquecer a auditoria de IA com mais dimensões operacionais, como endpoint e janela temporal avançada
- Registrar ao fim do próximo bloco qualquer ajuste necessário em documentação e inventário

## Arquivos relevantes do dia

- `docs/progresso2.md`
- `frontend/app/mensagens/page.tsx`
- `frontend/app/auditoria-ia/page.tsx`
- `frontend/components/app-shell.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/types.ts`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/next-env.d.ts`
- `src/infra/run_migrations.py`
- `migrations/001_initial_schema.sql`
- `fix_admin.py`
- `render.yaml`
- `scripts/seed_local_demo.py`
- `src/repositories/message_repository.py`
- `src/repositories/ai_audit_repository.py`
- `src/web/routes/api_v1.py`

## Bloqueios

- O interpretador global `python` não possui `Flask`; o backend local deve continuar sendo executado pelo virtualenv do projeto
- O teste visual completo no navegador ainda não foi automatizado nesta sessão; a validação autenticada foi fechada via API e CORS
- A recriação do banco em nuvem ainda depende de aplicar o blueprint corrigido no provedor

## Primeira missão sugerida para amanhã

- Aplicar o Blueprint do Render a partir do repositório `https://github.com/prosperidade/cannabia`
- Confirmar criação automática de `cannabia-db`, `cannabia-api` e `cannabia-frontend`
- Preencher os segredos obrigatórios no Render e validar o `preDeployCommand` das migrations
- Rodar smoke test do ambiente publicado com login, dashboard, mensagens e auditoria de IA
