# Staging Environment — Backlog

**Status atual:** sem staging persistente.
**Decisão Sprint 1 (Track D.4):** **adiar**. Substituído por este documento.
**Última atualização:** 2026-05-09 (Sprint 1, branch `feat/sprint-1-D-tactical`).

---

## Estado atual

- Apenas **prod** definido em `render.yaml` (services `cannabia-api`, `cannabia-frontend`, DB `cannabia-db`, todos `plan: starter` na região `ohio`).
- Sem environment de validação intermediário.
- Deploys vão direto pra `main` → produção (auto-deploy via `autoDeployTrigger: commit`).
- Suite local + CI cobrem o caminho funcional, mas **não há ambiente espelho de prod** pra validar interações com Render-specific (cold start, rede, env vars reais, dimensão de memória 512MB).

## Risco

Pré-investidor / pré-piloto com pacientes reais, **deploy direto a `main` é mid-risk**:

- Erro de migration na pré-deploy quebra prod.
- Diff de comportamento entre dev local (Docker compose, postgres local) e Render (managed Postgres + gunicorn+eventlet) só aparece em prod.
- Bug discoverable só com tráfego real → primeira observação é o paciente vendo a falha.

## Opções avaliadas (custo + esforço)

### Opção 1 — Render persistent staging
- Duplicar serviços `cannabia-api-staging` + `cannabia-frontend-staging` + DB `cannabia-db-staging`.
- Apontar pra branch `staging` (ou usar branch deploys do Render).
- **Custo:** ~$21/mês (api $7 + frontend $7 + DB basic-256mb $7).
- **Esforço:** 1-2h pra criar serviços + cabeçalho de docs.
- **Pró:** ambiente dedicado, persistente, fácil de demonstrar pra investidor.
- **Contra:** custo recorrente. Pra portfólio com múltiplos projetos pré-revenue, isso vira fricção.

### Opção 2 — Render Preview Environments (efêmero por PR)
- Render cria env temporário pra cada PR aberto.
- Custo proporcional ao tempo que PRs ficam abertos.
- **Esforço:** ~30min de configuração no `render.yaml` + revisão das envs sensíveis.
- **Pró:** custo proporcional, ambiente real por PR, smoke test integrado ao review.
- **Contra:** Não persiste; não dá pra "manter staging vivo" pra demo. Limitações de plano (Preview Environments podem exigir plan superior).

### Opção 3 — Staging container no R610 (homelab)
- Subir containers Docker no servidor R610 acessível via Tailscale.
- **Custo:** zero adicional (hardware já existe).
- **Esforço:** 4-6h (configurar docker-compose.staging.yml + reverse proxy + persistência).
- **Pró:** custo zero, controle total.
- **Contra:** R610 não é redundante; se cair, staging cai. Não simula 100% o Render (rede, latência, RAM constraints).

### Opção 4 — Skip permanente (status quo)
- Aceitar deploy direto a `main` como prática.
- Mitigação: smoke test pós-deploy + rollback rápido (revert + push).
- **Custo:** zero.
- **Esforço:** zero.
- **Pró:** simplicidade.
- **Contra:** o risco descrito acima permanece.

## Recomendação

**Re-avaliar em Sprint 4** (pré-investidor) ou **assim que o primeiro deploy quebrar produção** (gatilho operacional).

Critério para escolher entre as opções:

| Cenário | Opção recomendada |
|---|---|
| Pre-investidor com demo agendada | 1 (Render persistent) |
| Frequência alta de PRs com mudanças de schema | 2 (Preview Environments) |
| Custo é restrição forte e R610 está estável | 3 (R610 staging container) |
| Risco aceitável e equipe disciplinada com smoke pós-deploy | 4 (status quo) |

## Notas

- Track D.4 do Sprint 1 originalmente previa criar Opção 1. Decisão do coordenador (2026-05-09): **substituir por este doc** — cabe melhor numa sprint dedicada quando o critério de gatilho for atingido.
- Quando este backlog for retomado, o sub-agente que pegar a tarefa deve:
  1. Confirmar o cenário atual com o coordenador (qual gatilho disparou).
  2. Escolher entre as 4 opções com base no critério acima.
  3. Implementar + documentar em `docs/STAGING_ENVIRONMENT.md` (criar) com URLs, processo de deploy, processo de migrations.
