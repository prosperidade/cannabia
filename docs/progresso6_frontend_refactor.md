# Progresso 6 — Refatoracao Completa do Frontend + Integracao Backend

## Data
2026-04-07 / 2026-04-08

## Objetivo
Refatorar todo o frontend de CSS customizado (ds-*) para Tailwind CSS com Material Design 3, implementando 48 rotas para 4 personas (paciente, medico, organizacao, admin) baseadas em 82 telas desenhadas no Stitch.

## Trabalho Realizado

### Fase 0 — Fundacao
- Instalado Tailwind CSS v3 + PostCSS + tailwind-merge
- Criado tailwind.config.ts com 40+ tokens de cor Material Design 3
- Carregadas fontes Manrope (headlines) + Inter (body) + Material Symbols Outlined (icones)
- Criado stitch-utilities.css (glass-panel, glass-card, scrollbar, pulse-dot)
- Criados 3 layouts compartilhados: SidebarLayout (desktop), MobileLayout (mobile), WizardLayout (triagem)
- Criados 12 componentes UI primitivos em components/ui-tw/: Button, Card, Badge, Input, ToggleSwitch, SliderRange, StatCard, DataTable, Avatar, SearchBar, ProgressBar, MaterialIcon
- Criados 4 arquivos de tipos: types-triagem.ts, types-campaign.ts, types-telemetry.ts, types-org.ts
- Atualizado cn.ts para twMerge(clsx())

### Fase 1 — Fluxo Core de Receita (5 paginas)
- Wizard de Triagem: 7 steps completos (motivo, sintomas, dados fisicos, emocional, habitos, historico, revisao) com WizardEngine (state machine via Context)
- Checkout de Consulta: 4 etapas (info, pagamento PIX/cartao, confirmacao, sucesso)
- Dashboard do Medico: KPIs, analise IA botanica, prescricoes ativas, status fisico/emocional
- Fila de Atendimento: lista com busca, filtros por status/risco, cards com indicador de risco
- Consulta ao Vivo: split-view chat + painel IA com 4 tabs (analise, tratamento, evidencias, prontuario)

### Fase 2 — Workflow Clinico (12 paginas)
- Prescricao Digital ANVISA (receita branca/azul) com calculo IA
- Assinatura Digital com certificado ICP-Brasil
- Perfil do Paciente (prontuario completo, timeline clinica)
- Editor de Notas Medicas
- Retornos e Ajustes (painel de acompanhamento)
- Portal do Paciente (dashboard, meu tratamento, diario de sintomas)
- 5 telas avancadas: onboarding medico, inteligencia clinica, lab AI, ensaios clinicos, precisao botanica

### Fase 3 — Gestao Organizacional (12 paginas)
- Dashboard gerencial com KPIs e graficos
- Gestao de pacientes, medicos (2 tabs), agendamentos (com calendario)
- Campanhas WhatsApp (templates + execucoes)
- Estoque/dispensacao (2 tabs com alertas)
- Faturamento e inadimplencia
- Financeiro gerencial (P&L, repasses medicos)
- Personalizacao do perfil da clinica
- Relatorios BI (4 tabs: atendimentos, financeiro, pacientes, IA)
- Compliance ANVISA (checklist, auditoria digital)
- Historico de mensagens (API real)

### Fase 4 — Admin Plataforma (4 paginas)
- Dashboard admin com saude do sistema (useSystemStatus)
- Gestao de organizacoes (antigo tenants) com monitoramento real-time
- Gestao de usuarios e permissoes (matriz de roles)
- Auditoria de IA e controle de custos (API real getAiMetrics)

### Fase 5 — Polish
- Humanizacao de linguagem: 150+ termos tecnicos substituidos em 35+ arquivos
- Paginas antigas substituidas: /, /login, /dashboard, /atendimentos, /agendamentos, /mensagens, /auditoria-ia → redirects inteligentes por role
- Login unico com redirect por role (admin→/admin, medico→/med, atendente→/org, paciente→/p)
- Criadas paginas de lista faltantes: /med/atendimentos, /med/prescricao, /med/pacientes
- Corrigido sidebar overflow, mobile bottom nav com "Mais..."
- Criada pagina /settings
- Fix logout na org (chamava router.push sem limpar sessao)

### Integracao Backend
- Criados 3 novos arquivos de rotas Flask:
  - patient_portal.py: 5 endpoints (profile, treatment, diary GET/POST, evolution)
  - returns.py: 1 endpoint (returns with patients + AI recommendations)
  - org_management.py: 8 endpoints (dashboard, patients, doctors, stock, billing, financial)
- Registrados blueprints no app.py
- Conectadas 11 paginas frontend de mock → API real
- Adicionadas 12 funcoes ao lib/api.ts
- Corrigidas permissoes dos endpoints org (Admin-only → Admin+Medico+Atendente)

### Banco de Dados
- Criada migration 013: symptom_diary, stock_inventory, stock_dispensations, billing + expanded treatment_plans + patients.user_id/status + VIEW clinic_members
- Criado seed_comprehensive.py: ~200 registros demo (15 pacientes, 8 relatorios, 30 mensagens, etc.)
- Criado setup_local.py: orquestrador que roda migrations + seeds
- Criado seed_users.py: 4 usuarios (admin, medico, atendente, paciente) + vinculo clinica

## Decisoes Registradas
1. **Tailwind CSS v3** (nao v4) — compativel com Next.js 16 e CDN Tailwind do Stitch
2. **CSS legado mantido** — globals.css e design-system.css continuam funcionando para paginas nao migradas
3. **Endpoints com mock fallback** — novos endpoints retornam mock data do servidor quando tabelas nao existem, garantindo que frontend sempre recebe dados
4. **View clinic_members** — criada como alias para user_clinics, evitando fix em multiplos endpoints
5. **Linguagem humanizada** — termos tecnicos (tokens, pipeline, RAG, tenants, etc.) substituidos por linguagem do usuario final
6. **Login unico** — mesma tela /login para todos os perfis, redirect automatico por role

## Metricas
- 48 rotas no frontend (de 12 originais)
- 82 telas Stitch como referencia (47 desktop + 32 mobile + 3 system)
- 39 tabelas no banco de dados
- ~200 registros de seed demo
- 14 endpoints novos no backend
- Build Next.js limpo (0 erros TypeScript)

## Proximos Passos
1. Rodar setup_local.py com banco PostgreSQL local e validar dados em todas as paginas
2. Configurar banco de producao (Supabase free tier como alternativa ao Render)
3. Integrar agentes de IA (pipeline clinico, RAG com ChromaDB, prescricao inteligente)
4. Testes end-to-end do fluxo completo: triagem → consulta → prescricao → acompanhamento
5. Deploy em producao (Render backend + Vercel/Render frontend)

## Arquivos Relevantes

### Frontend (novos)
- frontend/tailwind.config.ts — config MD3
- frontend/app/stitch-utilities.css — glass effects
- frontend/components/layouts/*.tsx — 3 layouts
- frontend/components/ui-tw/*.tsx — 12 primitivos
- frontend/components/triagem/*.tsx — wizard 7 steps + engine
- frontend/app/med/**/*.tsx — 13 paginas medico
- frontend/app/org/**/*.tsx — 12 paginas organizacao
- frontend/app/admin/**/*.tsx — 4 paginas admin
- frontend/app/p/**/*.tsx — 4 paginas paciente
- frontend/app/triagem/**/*.tsx — wizard
- frontend/lib/types-*.ts — 4 arquivos de tipos

### Backend (novos)
- src/web/routes/patient_portal.py
- src/web/routes/returns.py
- src/web/routes/org_management.py
- migrations/013_missing_tables_and_columns.sql
- scripts/seed_comprehensive.py
- scripts/seed_users.py
- scripts/setup_local.py
