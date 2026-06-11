# FAXINA DE BRANCHES — Fase 1: Inventário (read-only)

**Versão:** v1.0 | **Data:** 2026-06-10 | **Commit base (main):** `76cabe4`
**Natureza:** inventário read-only. **NENHUMA branch/worktree foi deletada.** A deleção é a Fase 2, executada só após decisão expressa do Andre, por classe (A em bloco; B e C item a item).
**Governança:** 29.G. Escrita autorizada: somente este arquivo, na branch `faxina/inventario-branches`, via PR.

## Legenda de classes
- **A — mergeada em `main`** → deleção segura (conteúdo já está na main).
- **B — não mergeada, superada/abandonada** → sem valor (justificativa de 1 linha).
- **C — não mergeada, conteúdo potencialmente valioso** → descrita; decisão item a item. *Em dúvida entre B e C, classifiquei C.*

Protegidas (fora da faxina): `main`, `faxina/inventario-branches` (esta sessão), `consolidacao/30-plano-remediacao` (**PR #65 aberto, trabalho ativo**).

---

## 1. Worktrees (`git worktree list`)

5 worktrees vivos em `.claude/worktrees/`, todos **locked** e **limpos** (working tree sujo = 0). **Atenção:** as branches que eles seguram são `feat/sprint-3-*` — NÃO os branches locais homônimos `worktree-agent-*` (esses são branches livres, ver §2). Deletar a branch sem remover o worktree antes deixa lixo no filesystem.

| Worktree (path) | Branch ocupada | Último commit | Sujo? | Branch é classe |
|---|---|---|---|---|
| `.claude/worktrees/agent-a5bca0e4193ebc032` | `feat/sprint-3-Legislacao-hardening` | `c9b90de` (11/05) | limpo | **A** (mergeada) |
| `.claude/worktrees/agent-a63758948d0c363b5` | `feat/sprint-3-Page-migration-tier2` | `ef5cc69` (11/05) | limpo | **A** (mergeada) |
| `.claude/worktrees/agent-aba9fedfaaaed8717` | `feat/sprint-3-CFD-cientifico-final-dosagem` | `414e97d` (11/05) | limpo | **A** (mergeada) |
| `.claude/worktrees/agent-ad5d942301a73b659` | `feat/sprint-3-Obs-harden` | `331ee12` (11/05) | limpo | **A** (mergeada) |
| `.claude/worktrees/agent-af2dc16a95b6f5c87` | `feat/sprint-3-SCC-I1-integrity-timestamps` | `764face` (12/05) | limpo | **C** (não mergeada) |

> Os 4 primeiros seguram branches **já mergeadas** — o worktree pode ser removido sem perda. O 5º segura a única branch `feat/sprint-3-*` **não mergeada** (classe C, §3) — remover o worktree é seguro (conteúdo está na branch/remoto), mas a *branch* só some na Fase 2 por decisão item a item.

---

## 2. Branches LOCAIS (13, fora das protegidas)

| Branch | Último commit | Mergeada? | Classe | Síntese | Recomendação |
|---|---|---|---|---|---|
| `feat/sprint-3-Legislacao-hardening` | `c9b90de` 11/05 | SIM | **A** | =remota mergeada; presa em worktree | Remover worktree → deletar |
| `feat/sprint-3-Page-migration-tier2` | `ef5cc69` 11/05 | SIM | **A** | idem | Remover worktree → deletar |
| `feat/sprint-3-CFD-cientifico-final-dosagem` | `414e97d` 11/05 | SIM | **A** | idem | Remover worktree → deletar |
| `feat/sprint-3-Obs-harden` | `331ee12` 11/05 | SIM | **A** | idem | Remover worktree → deletar |
| `feat/sprint-3-SCC-I1-integrity-timestamps` | `764face` 12/05 | **NÃO** (ahead 1) | **C** | presa em worktree; 1 commit único (doc de sprint SCC + rollback) — ver §3 | Decisão item a item |
| `feat/sprint-A-baseline-recoverability` | `04f4ae1` 25/05 | SIM | **A** | livre | `git branch -d` |
| `feat/sprint-B-secrets-financial` | `550e188` 25/05 | SIM | **A** | livre | `git branch -d` |
| `feat/sprint-C-mvp-pilot` | `aff7ae9` 25/05 | SIM | **A** | livre | `git branch -d` |
| `worktree-agent-a5bca0e4193ebc032` | `e2f9c39` 11/05 | SIM | **A** | **branch livre** (não é worktree); aponta p/ commit de docs de fechamento sprint-2 (mergeado) | `git branch -d` |
| `worktree-agent-a63758948d0c363b5` | `e2f9c39` 11/05 | SIM | **A** | idem | `git branch -d` |
| `worktree-agent-aba9fedfaaaed8717` | `e2f9c39` 11/05 | SIM | **A** | idem | `git branch -d` |
| `worktree-agent-ad5d942301a73b659` | `e2f9c39` 11/05 | SIM | **A** | idem | `git branch -d` |
| `worktree-agent-af2dc16a95b6f5c87` | `e2f9c39` 11/05 | SIM | **A** | idem | `git branch -d` |

> Os 5 `worktree-agent-*` locais convergem todos para `e2f9c39` ("docs(sprint-2): consolidado de fechamento") — já em `main`. São restos de worktrees antigos cuja referência de branch ficou para trás; **não há worktree vivo associado a eles** (confirmado: `git worktree list` não os lista). Deleção trivial.

---

## 3. Branches REMOTAS (38, fora das protegidas)

### 3.1 Classe A — mergeadas em `main` (25) → deleção segura em bloco

| Branch remota | Último commit |
|---|---|
| `origin/codex/complete-analysis-and-improvement-suggestions` | `3551d9d` 10/02 |
| `origin/codex/complete-analysis-and-improvement-suggestions-ee8u56` | `e1a292e` 10/02 |
| `origin/codex/complete-analysis-and-improvement-suggestions-jkc9vu` | `035b112` 10/02 |
| `origin/codex/generate-comprehensive-documentation-for-flask-app` | `874ed9e` 21/02 |
| `origin/codex/update-database_schema.md-documentation` | `1e0214c` 22/02 |
| `origin/feat/cannabia-docs-4821243085080745684` | `fd81659` 01/03 |
| `origin/feat/sprint-1-A-3-pii-redaction` | `aae1237` 10/05 |
| `origin/feat/sprint-1-A-4-hardening` | `3b4cd8e` 10/05 |
| `origin/feat/sprint-1-A-security-lgpd` | `5d4c054` 10/05 |
| `origin/feat/sprint-1-C-1-prescritor-flow` | `779cf11` 10/05 |
| `origin/feat/sprint-1-C-2-mempalace-extirpation` | `dd01d44` 10/05 |
| `origin/feat/sprint-2-AI-anamnesis-extension` | `1f6b0fe` 10/05 |
| `origin/feat/sprint-2-Audit-empty-to-error` | `6a3f495` 11/05 |
| `origin/feat/sprint-2-LGPD-purge-retention` | `42dd58c` 11/05 |
| `origin/feat/sprint-2-Obs-sentry` | `51e412a` 10/05 |
| `origin/feat/sprint-2-Page-pagination` | `be539c1` 10/05 |
| `origin/feat/sprint-2-Reg-prompt-registry` | `b7e55d3` 11/05 |
| `origin/feat/sprint-3-CFD-cientifico-final-dosagem` | `414e97d` 11/05 |
| `origin/feat/sprint-3-Legislacao-hardening` | `c9b90de` 11/05 |
| `origin/feat/sprint-3-Obs-harden` | `331ee12` 11/05 |
| `origin/feat/sprint-3-Page-migration-tier2` | `ef5cc69` 11/05 |
| `origin/feat/sprint-A-baseline-recoverability` | `04f4ae1` 25/05 |
| `origin/feat/sprint-B-secrets-financial` | `550e188` 25/05 |
| `origin/feat/sprint-C-mvp-pilot` | `aff7ae9` 25/05 |
| `origin/pr/security-hardening` | `9402819` 20/02 |

### 3.2 Classe B — não mergeadas, superadas/abandonadas (4) → sem valor

| Branch remota | Commits únicos | Por que não tem valor (1 linha) |
|---|---|---|
| `origin/codex/complete-analysis-and-improvement-suggestions-26u5sp` | "Documenta estratégia de reabertura de PR limpo" | Fork da raiz (10/02) com o **layout monolítico pré-refatoração** (`src/main.py`, `src/auth.py`, `src/database.py` achatados) — toda a árvore foi reescrita para `src/web/routes`+`services`+`ai`; o único delta é doc de processo (`CONFLICT_PLAYBOOK.md`) + lixo (`report_patient_1.pdf`, `Prompt atualizado.docx`). |
| `origin/codex/complete-analysis-and-improvement-suggestions-2qxhp3` | "Adiciona resolução guiada para conflitos" + `scripts/resolve_conflicts_now.sh` | Idem — playbook de merge (`MERGE_CONFLICT_RESOLUTION.md`) sobre o código antigo; obsoleto. |
| `origin/codex/complete-analysis-and-improvement-suggestions-hjsz3s` | "playbook e helper para resolver conflitos" (2 commits) | Idem — mesma base monolítica + playbook de conflito; superado. |
| `origin/codex/complete-analysis-and-improvement-suggestions-qg4dqv` | "Define estratégia de PR fatiado" + `PR_FATIADO_PLAN.md` | Idem — doc de estratégia de PR sobre código pré-refatoração; obsoleto. |

> Os 4 compartilham merge-base `e1a292e` (10/02, infância do repo). O alto número de arquivos no diff (34–37) é artefato do fork antigo (carregam a árvore inteira da época), **não** trabalho de produto novo. Siblings `-ee8u56`/`-jkc9vu` desse mesmo experimento foram mergeados (classe A).

### 3.3 Classe C — não mergeadas, conteúdo potencialmente valioso (9) → decisão item a item

| Branch remota | Commits únicos / arquivos | O que existe e por que pode importar |
|---|---|---|
| `origin/feat/sprint-3-SCC-I1-integrity-timestamps` | 1 commit; `docs/sprints/sprint_3_SCC_I1.md` (**+549 linhas, novo**) + `docs/22` (1 linha) | Doc de execução da sprint que aplicou as **migrations 022+023** (integridade/timestamps do SCC) em dev, **com plano de rollback**. As migrations já estão na `main`, mas o **rollback plan** e o registro de execução podem não estar capturados em outro lugar. ⚠️ Existe também como **branch local + worktree** (`agent-af2dc16a…`). Verificar se o conteúdo foi absorvido em `docs/22`/`BACKLOG_SCC.md` antes de deletar. |
| `origin/codex/update-project-documentation-for-current-architecture` | 9 commits; `README.md` (+228), `docs/DOCUMENTACAO_SISTEMA.md`, `src/app.py` (+79), `src/templates/login.html` (+67) etc. | Branch "guarda-chuva" da linha codex: agrega os experimentos de auth (CSRF, security headers, cookie hardening) **+** reescrita de README/arquitetura. Tudo sobre o **código legado Jinja/monólito**. Provavelmente superado pela refatoração de auth (`pr/security-hardening`, mergeada) e pela série de docs `07–20`; confirmar com um diff antes de deletar. |
| `origin/codex/generate-comprehensive-documentation-for-flask-app-pgb6jf` | 1 commit; **+1372 linhas** em 6 docs: `AI_MODULE_DOCUMENTATION.md`, `AUTHORIZATION_AND_MULTI_TENANCY.md`, `DATABASE_SCHEMA.md`, `DEPLOYMENT_AND_PRODUCTION_GUIDE.md`, `SYSTEM_ARCHITECTURE.md`, `README.md` | Reescrita ampla de documentação de arquitetura ("to match current codebase"). A versão sem sufixo está mergeada; esta é alternativa não aplicada. Pode conter recortes (multi-tenancy, deployment) úteis; skim antes de deletar — risco baixo de perda real porque a série `docs/07–16` cobre os mesmos temas com mais maturidade. |
| `origin/codex/add-csrf-protection-to-login-form` | 1 commit único: "Add CSRF validation to login form" (`login.html`+`app.py`) | Experimento de auth (10–11/02) sobre o login legado. **CSRF já está presente na `main`** (token em mutações — evidência 29.7 §1.3). Quase certamente superado; diff rápido para confirmar e deletar. |
| `origin/codex/add-csrf-protection-to-login-form-i3gtyz` | "Add login-only rate limiting for POST" | Rate limiting no POST de login. **Rate limit já existe na `main`** (`auth.py:28-31`, 60/min — evidência 29.3 P8). Provável redundância; confirmar e deletar. |
| `origin/codex/add-csrf-protection-to-login-form-v00nsf` | "Add global HTTP security headers in after_request" | **Security headers globais** no `after_request`. Não confirmado explicitamente nos relatórios da Onda 1 — **vale um grep em `src/` por headers (CSP/HSTS/X-Frame) antes de deletar**; se ausente na main, é o item de maior valor potencial deste cluster. |
| `origin/codex/add-csrf-protection-to-login-form-vupc6e` | "Harden Flask session cookie configuration" | **Hardening de cookie de sessão** (Secure/HttpOnly/SameSite). Verificar configuração de cookie atual na `main` antes de deletar. |
| `origin/codex/add-session-based-login-with-flask-login` | "Avoid binary requirements diff by isolating auth deps" (`requirements-auth.txt`) | Base do login Flask-Login + isolamento de deps de auth. Fundação dos demais; superada pela refatoração de auth mergeada. Diff de confirmação. |
| `origin/codex/add-session-based-login-with-flask-login-wecqrw` | "Add CSRF protection for Flask forms" (+`src/extensions.py`) | Variante com `extensions.py` e CSRF de formulários. Mesma família; provável redundância pós-refatoração. |

> **Veredicto do cluster auth-codex (6 branches):** são iterações de fev/2026 que precederam a refatoração consolidada de autenticação (`pr/security-hardening`, mergeada). CSRF e rate-limiting já estão na `main` (evidência 29.3/29.7). Os dois itens que merecem um olhar real antes de descartar são **security headers** (`v00nsf`) e **cookie hardening** (`vupc6e`). Mantidos em C por prudência (não subestimar segurança), com recomendação de diff por feature.

---

## 4. Resumo quantitativo

| Classe | Local | Remota | Total |
|---|---|---|---|
| **A** (mergeada — deleção segura) | 12 | 25 | **37** |
| **B** (sem valor — deletar após confirmar) | 0 | 4 | **4** |
| **C** (potencial valor — decisão item a item) | 1¹ | 9² | **9 distintas** |
| Worktrees a remover | — | — | **5** (4 sobre branches A, 1 sobre branch C) |

¹ A branch local C (`feat/sprint-3-SCC-I1-integrity-timestamps`) é a mesma da remota C — contada uma vez no total de C.
² Inclui a remota SCC-I1. Total de identidades C distintas = 9.

---

## 5. Comandos de deleção — PRONTOS, **NÃO EXECUTADOS** (Fase 2)

> ⚠️ Nada abaixo foi rodado. Executar só após decisão do Andre, por classe. **Sempre remover o worktree ANTES de deletar a branch que ele ocupa.**

### Passo 0 — Remover worktrees (pré-requisito; locked → usar `--force`, todos limpos)
```bash
# 4 worktrees sobre branches CLASSE A (seguro):
git worktree remove --force .claude/worktrees/agent-a5bca0e4193ebc032   # Legislacao-hardening
git worktree remove --force .claude/worktrees/agent-a63758948d0c363b5   # Page-migration-tier2
git worktree remove --force .claude/worktrees/agent-aba9fedfaaaed8717   # CFD-cientifico-final-dosagem
git worktree remove --force .claude/worktrees/agent-ad5d942301a73b659   # Obs-harden
# 1 worktree sobre branch CLASSE C (só se Andre aprovar deletar a SCC-I1):
git worktree remove --force .claude/worktrees/agent-af2dc16a95b6f5c87   # SCC-I1-integrity-timestamps
git worktree prune
```

### CLASSE A — LOCAIS (após Passo 0 para as 4 em worktree)
```bash
# Livres:
git branch -d feat/sprint-A-baseline-recoverability
git branch -d feat/sprint-B-secrets-financial
git branch -d feat/sprint-C-mvp-pilot
git branch -d worktree-agent-a5bca0e4193ebc032
git branch -d worktree-agent-a63758948d0c363b5
git branch -d worktree-agent-aba9fedfaaaed8717
git branch -d worktree-agent-ad5d942301a73b659
git branch -d worktree-agent-af2dc16a95b6f5c87
# Eram worktrees (deletar após Passo 0):
git branch -d feat/sprint-3-Legislacao-hardening
git branch -d feat/sprint-3-Page-migration-tier2
git branch -d feat/sprint-3-CFD-cientifico-final-dosagem
git branch -d feat/sprint-3-Obs-harden
```

### CLASSE A — REMOTAS (deleção em bloco)
```bash
git push origin --delete \
  codex/complete-analysis-and-improvement-suggestions \
  codex/complete-analysis-and-improvement-suggestions-ee8u56 \
  codex/complete-analysis-and-improvement-suggestions-jkc9vu \
  codex/generate-comprehensive-documentation-for-flask-app \
  codex/update-database_schema.md-documentation \
  feat/cannabia-docs-4821243085080745684 \
  feat/sprint-1-A-3-pii-redaction \
  feat/sprint-1-A-4-hardening \
  feat/sprint-1-A-security-lgpd \
  feat/sprint-1-C-1-prescritor-flow \
  feat/sprint-1-C-2-mempalace-extirpation \
  feat/sprint-2-AI-anamnesis-extension \
  feat/sprint-2-Audit-empty-to-error \
  feat/sprint-2-LGPD-purge-retention \
  feat/sprint-2-Obs-sentry \
  feat/sprint-2-Page-pagination \
  feat/sprint-2-Reg-prompt-registry \
  feat/sprint-3-CFD-cientifico-final-dosagem \
  feat/sprint-3-Legislacao-hardening \
  feat/sprint-3-Obs-harden \
  feat/sprint-3-Page-migration-tier2 \
  feat/sprint-A-baseline-recoverability \
  feat/sprint-B-secrets-financial \
  feat/sprint-C-mvp-pilot \
  pr/security-hardening
```

### CLASSE B — REMOTAS (item a item, após confirmação)
```bash
git push origin --delete codex/complete-analysis-and-improvement-suggestions-26u5sp
git push origin --delete codex/complete-analysis-and-improvement-suggestions-2qxhp3
git push origin --delete codex/complete-analysis-and-improvement-suggestions-hjsz3s
git push origin --delete codex/complete-analysis-and-improvement-suggestions-qg4dqv
```

### CLASSE C — só por decisão expressa, item a item (após diff de confirmação)
```bash
# SCC-I1 (remota + local + worktree no Passo 0):
git push origin --delete feat/sprint-3-SCC-I1-integrity-timestamps
git branch -D feat/sprint-3-SCC-I1-integrity-timestamps   # -D: não mergeada
# Docs:
git push origin --delete codex/update-project-documentation-for-current-architecture
git push origin --delete codex/generate-comprehensive-documentation-for-flask-app-pgb6jf
# Auth-codex (recomendado: diff de security-headers e cookie-hardening antes):
git push origin --delete codex/add-csrf-protection-to-login-form
git push origin --delete codex/add-csrf-protection-to-login-form-i3gtyz
git push origin --delete codex/add-csrf-protection-to-login-form-v00nsf
git push origin --delete codex/add-csrf-protection-to-login-form-vupc6e
git push origin --delete codex/add-session-based-login-with-flask-login
git push origin --delete codex/add-session-based-login-with-flask-login-wecqrw
```

### Higiene final (após qualquer bloco)
```bash
git fetch --prune
git worktree prune
git branch -a   # conferir: só main + branches ativas
```

---

*Fim da Fase 1. A Fase 2 (deleção) só começa após decisão do Andre, por classe. Este relatório é o único artefato escrito desta sessão.*
