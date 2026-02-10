# Plano de PR Fatiado (recomendado para destravar conflitos)

Quando um PR grande trava em conflitos, a estratégia mais segura é enviar em etapas pequenas e independentes.

## Ordem recomendada de PRs

### PR 1 — Infra e baseline
Arquivos:
- `.gitattributes`
- `.env.example`
- `migrations/001_initial_schema.sql`
- `src/config.py`
- `src/database.py`
- `src/run_migrations.py`

Objetivo:
- padronizar ambiente e base técnica sem mexer em comportamento de tela.

### PR 2 — Segurança transversal
Arquivos:
- `src/auth.py`
- `src/security.py`
- `src/app.py` (somente login/sessão/headers)

Objetivo:
- aprovar controles P0 isoladamente (RBAC/CSRF/session hardening/redaction).

### PR 3 — Camadas de domínio
Arquivos:
- `src/repositories/*`
- `src/services/*`
- `src/integrations/*`
- `src/notifications.py`
- `src/whatsapp_template.py`

Objetivo:
- consolidar arquitetura em camadas sem misturar UI.

### PR 4 — Rotas principais
Arquivos:
- `src/realtime_notifications.py`
- `src/dashboard.py`
- `src/historico_atendimento.py`
- `src/scheduling_chain.py`
- `src/webhook.py`

Objetivo:
- migrar uso das camadas para as rotas, já com base aprovada.

### PR 5 — Templates/UI
Arquivos:
- `src/templates/dashboard.html`
- `src/templates/index.html`
- `src/templates/login.html`
- `src/templates/scheduling_dashboard.html`

Objetivo:
- resolver conflitos visuais por último, quando backend estiver estável.

### PR 6 — Documentação operacional
Arquivos:
- `docs/DOCUMENTACAO_SISTEMA.md`
- `docs/SECURITY_MODEL.md`
- `docs/CONFLICT_PLAYBOOK.md`
- `docs/MERGE_CONFLICT_RESOLUTION.md`

Objetivo:
- documentar estado final aprovado, evitando retrabalho durante implementação.

## Regras de merge para reduzir conflito
- Sempre rebasear branch de feature na base atual antes de abrir PR.
- Evitar PR com mais de ~12 arquivos quando possível.
- 1 tema por PR (infra, segurança, domínio, rotas, UI, docs).
- Se houver conflito em >5 arquivos, fechar e reabrir PR fatiado.
