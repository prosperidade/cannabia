# Política de Backup e Disaster Recovery

## Status

- **Vigência**: 2026-04-19
- **Escopo**: produção (Render) e ambientes de staging.
- **Relacionado**: `migrations/down/README.md` (rollback de schema), `docs/runbook.md` (operação), `docs/BACKLOG_SCC.md` (P0.5 — origem desta política), `docs/10_SECURITY_COMPLIANCE_AND_AUDIT.md` (invariantes do Art. 17).

## 1. Escopo e responsabilidades

| Componente | O que é | Backup automático | Responsável |
|---|---|---|---|
| PostgreSQL — schema + dados | Fonte autoritativa de prontuários, auditoria, tenants, traceability | Sim (Render Managed Postgres) | Ops |
| ChromaDB (`chroma_db/`) | Vetores de conhecimento — **derivável** da base relacional e dos PDFs | Não | Ops — rebuild via `scripts/ingest_knowledge.py` |
| Código-fonte | Repositório Git em `github.com/prosperidade/cannabia` | Sim (GitHub) | Dev |
| Configuração (`.env` em produção) | Secrets injetados pelo Render, não versionados | Sim (Render vault) | Ops |
| Arquivos legislativos (`data/legislation/`) | Fontes originais já publicadas (ANVISA, CFM, Planalto) | Não — re-download via `scripts/download_legislation_sources.ps1` | Ops |

**Dado crítico hardcoded como invariante (Art. 17)**: prontuários, trilha de auditoria (`audit_trail`, `ai_audit_logs`), `traceability_events` (SCC — futuro) e registros de farmacovigilância (SCC — futuro). Esses dados **nunca** podem ser perdidos por erro operacional sem possibilidade de recuperação.

## 2. Objetivos (RPO/RTO)

| Ambiente | RPO (perda máxima aceitável) | RTO (tempo máximo de recuperação) |
|---|---|---|
| Produção | **24 h** (cadência atual de backup diário Render) | **4 h** |
| Staging | 72 h | 8 h |

Metas conservadoras para a fase atual. Quando o SCC (Fase 5 de imutabilidade + ancoragem em blockchain) estiver em produção, o RPO para `traceability_events` e `blockchain_anchors` precisa cair para **1 h** ou menos, por imposição do Art. 17. Reavaliar a cadência de backup ao entrar na Fase 5.

## 3. Cobertura de backup

### 3.1. PostgreSQL (Render Managed)

- **Cadência**: snapshots diários automáticos do plano Render (verificar plano atual no painel — Starter tem retenção de 7 dias).
- **Tipo**: snapshot físico, restauração em nova instância via painel Render ou API.
- **Ponto-em-tempo (PITR)**: depende do tier do plano Postgres contratado. Produção **deve** rodar em um tier que suporte PITR, com retenção mínima de 7 dias.
- **Snapshots on-demand**: exigidos antes de qualquer janela de manutenção agendada. Registrar em `docs/progressoN.md` do dia com o ID do snapshot.

### 3.2. Export lógico mensal (responsabilidade do operador)

Adicional ao backup físico gerenciado, uma vez por mês o operador deve fazer dump lógico e armazenar off-site (outro provedor, fora do Render):

```bash
pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" \
  -f "backups/cannabia-$(date +%Y%m%d).dump"
```

Retenção recomendada do dump off-site: 12 meses. Quando o SCC entrar, avaliar retenção regulatória mais longa (ANVISA historicamente exige 5 anos para registros farmacêuticos).

## 4. Procedimento de restauração

### 4.1. Restauração completa (perda total do banco)

1. Identificar o snapshot mais recente viável (Render → painel do Postgres → Backups).
2. Criar **nova instância** Postgres a partir do snapshot (não restaurar in-place — preserva o banco atual caso o snapshot esteja corrompido).
3. Apontar `DATABASE_URL` do serviço web para a nova instância.
4. Validar integridade com:
   ```bash
   psql "$DATABASE_URL" -c "SELECT version, filename FROM schema_migrations ORDER BY version"
   psql "$DATABASE_URL" -c "SELECT count(*) FROM patients"
   psql "$DATABASE_URL" -c "SELECT count(*) FROM anamnesis_reports"
   ```
5. Rebuild do ChromaDB via `python scripts/ingest_knowledge.py` (não tem backup — derivável).
6. Confirmar `/api/v1/health` retorna `healthy`.
7. Registrar em `docs/progressoN.md` do dia: snapshot usado, ID da instância antiga, tempo real de RTO.

### 4.2. Restauração seletiva (corrupção parcial / operação errada)

- **Preferir** restaurar um snapshot em instância temporária e copiar seletivamente as rows afetadas via `pg_dump -t tabela` + `psql` na instância de produção.
- **Não** restaurar in-place em produção — o resto dos dados mais novos seria sobrescrito.

### 4.3. Quando usar rollback de schema (migrations/down) em vez de restore

- **Rollback DDL** cabe para reverter uma migration recém-aplicada que quebrou o schema sem perda de dados. Ver `migrations/down/README.md`.
- **Restore** é o caminho para qualquer perda de dados — rollback de schema **não** recupera rows já destruídas ou alteradas.

## 5. Testes de recuperação

Ritualização trimestral mínima:

- Restaurar o snapshot mais recente em instância temporária.
- Rodar suite de smoke (`pytest tests/test_health.py`, `pytest tests/test_migrations.py`).
- Validar que `schema_migrations` está intacto e `SELECT 1` retorna em < 500 ms.
- Medir RTO real e comparar com a meta (§2).
- Documentar o teste em `docs/progressoN.md` do dia.

O primeiro teste formal fica como item aberto da Fase 0 do backlog (relacionado a P0.5) e deve ser executado até **2026-05-19** (um mês após a criação desta política).

## 6. Incidentes — comunicação mínima

Qualquer incidente que exija acionar esta política (restauração, rollback de schema em produção, perda confirmada de dados) precisa gerar:

1. Entrada em `docs/progressoN.md` do dia do incidente — seção "Bloqueios".
2. RCA (root cause analysis) curto (1 página) em `docs/rca/YYYY-MM-DD-<slug>.md` até 72 h após a mitigação.
3. Atualização desta política se algum procedimento se mostrar insuficiente.

## 7. Pontos em aberto

- Automatizar o dump lógico mensal via cron no Render ou GitHub Actions (hoje é manual).
- Avaliar cadência de backup quando Fase 5 do SCC (ancoragem blockchain) entrar — RPO de 1 h provavelmente exige tier Pro do Postgres Render ou migração para gerenciamento próprio.
- Definir fornecedor e bucket do armazenamento off-site para o dump mensal (atualmente não designado).
- Definir política formal de retenção regulatória para dados do SCC (decisão humana pendente no `docs/BACKLOG_SCC.md` §4, item 5).
