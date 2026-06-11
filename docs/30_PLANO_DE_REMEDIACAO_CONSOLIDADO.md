# 30 — Plano de Remediação Consolidado (CannabIA)

**Versão:** v1.0 | **Data:** 2026-06-10 | **Commit base:** `76cabe4`
**Entrada:** os 7 relatórios da Onda 1 (`docs/29.1`–`29.7`), todos mergeados na `main` (PRs #57–#63).
**Método:** cruzamento dos 7 backlogs, reconciliação de dependências contra o **alicerce (29.1 Tenancy)**, sequenciamento em ondas de 30/60/90 dias.
**Natureza:** plano. Nada implementado aqui. Cada item aponta o relatório-fonte e seu ID original.

> **Lembrete permanente (vale para todo o programa):** prontidão regulatória ≠ aprovação regulatória. Aprovar via/concentração/produto/sandbox é prerrogativa da Anvisa. Tudo abaixo prepara a plataforma; nada presume autorização.

---

## 1. Sumário executivo

A Onda 1 confirmou o veredicto da auditoria de abr/2026 com precisão de código: a CannabIA está **apta a operação controlada, não pronta para uso intensivo**. Mais importante, os 7 mergulhos convergiram para um padrão que não era óbvio relatório a relatório — **a maior parte das fragilidades críticas tem a mesma raiz e a mesma cura**:

1. **Existe muito mais sistema construído do que os backlogs registravam.** Fila RQ (`tasks.py`), billing com metering enforced (010), campanhas (011), versionamento de migrations (`schema_migrations`), 2 workers, hash-chain de rastreabilidade (028–030), Merkle de ancoragem — tudo existe em código e estava marcado como "ausente" ou "1 worker" em documentos. Vários mergulhos corrigiram premissas desatualizadas da auditoria (29.1 §1.1, 29.3 B.7, 29.6 billing, 29.7 deps, 29.5 C3). **Conclusão estratégica: a remediação é mais de *ativar e ligar* do que de *construir do zero*.**

2. **Um único item destrava cinco hubs: a fila assíncrona em produção.** A infra RQ está pronta mas não deployada (sem Redis no `render.yaml`, `enqueue_ai_task` nunca chamado). Pipeline de IA, webhook WhatsApp, e-mail, motor de SLA clínico, ancoragem blockchain e jobs financeiros **todos** dependem dela. É a **chave-de-abóbada** do plano (§4).

3. **Há perda de dados e vazamento cross-tenant acontecendo agora.** Mensagens duplicadas/descartadas (29.3 P1/P3), respostas de follow-up clínico jogadas fora (29.2 C1), webhook caindo sempre na clínica default (29.3 P4). São P0 baratos — entram na Onda 1.

4. **Há um prazo externo que não controlamos: 04/08/2026 (vigência das RDCs).** Faltam ~55 dias. A prontidão regulatória clínica (29.2 REG-1..8) e a ingestão dos textos das RDCs (29.5 F8.1, que também destrava o RAG regulatório e o 29.2 REG-5) precisam aterrissar dentro das Ondas 1–2. O **edital do sandbox** (29.5) não tem data e fura a fila quando sair.

**Ordem inviolável (decisão 10/06/2026, MEMORIA_VIVA §4):** diagnóstico → **remediação** → expansão. Este documento é a remediação. Nenhum hub novo (Agro/Jurídico/Farmácia/Pesquisa) antes do fim da Onda 3.

---

## 2. Reconciliação contra o alicerce (29.1) — invariantes de arquitetura

O 29.1 é o relatório de referência; os outros 6 reconciliam-se contra ele. Quatro decisões de arquitetura governam todo o sequenciamento:

| # | Invariante reconciliada | Origem | Consequência para o plano |
|---|---|---|---|
| INV-1 | **Toda operação longa/externa passa a ser assíncrona via RQ.** Provisão da fila é pré-requisito físico, não opcional. | 29.1 C3/R3; 29.3 RM3; 29.4 R4; 29.2 SLA; 29.5 R7; 29.6 R4/R8 | INFRA-1 (provisão) abre a Onda 1; os *cutovers* síncrono→assíncrono ficam na Onda 2, após a infra provada em produção. |
| INV-2 | **Código novo escreve `tenant_id`; a migração do legado `clinic_id`→`tenant_id` é o grande esforço faseado da Onda 3.** Duas gerações de schema convivem (legado clínico `clinic_id`-only × SCC/billing/payments tenant-native). | 29.1 C2/R4; 29.6 M4; 29.3 P4 | Nenhum hub "conserta" tenant sozinho. A resolução de tenant do webhook (29.3 RM5) entra na Onda 1 **sem** depender do RBAC profundo; o RBAC tenant-aware (29.1 R1) é Onda 2; a migração das tabelas clínicas (29.1 R4) é Onda 3, reconciliada com 29.2. |
| INV-3 | **Integridade referencial antes de migração transacional.** FKs do eixo tenant e dos domínios novos faltam (29.1 C4; 29.6 A4). | 29.1 R2; 29.6 R6 | FKs (aditivas, baratas, com limpeza de órfãos) entram na Onda 1 como fundação de todo o resto. |
| INV-4 | **O profissional multi-tenant é destino, não ponto de partida.** Habilitá-lo cria risco LGPD de visão cross-tenant que hoje não existe (porque não há cross-tenant real). | 29.1 F1/§6 | Modelo de vínculos (29.1 F1) só na Onda 3, sobre RBAC (R1) + sessão por tenant (R7), com filtro de tenant ativo obrigatório em toda query clínica. |

---

## 3. Temas transversais (o que se repete entre hubs)

Cada tema agrupa achados de múltiplos relatórios que devem ser remediados juntos para não retrabalhar:

- **T1 — Fila assíncrona (chave-de-abóbada).** 29.1 C3 · 29.3 P2/P9/P11 · 29.4 A4 · 29.2 (SLA/lembretes) · 29.5 A6 · 29.6 (jobs).
- **T2 — Isolamento multi-tenant.** 29.1 C1/C2/C4 · 29.3 P4 · 29.4 C2 (RAG global) · 29.6 M4.
- **T3 — Resiliência do pipeline de mensagens (perda de dados P0).** 29.3 R1/R2/R3 · 29.2 C1 (loop de follow-up).
- **T4 — Governança de IA nos canais do paciente.** 29.4 C1 (sem guardrails/billing/audit no WhatsApp+Triagem) · 29.3 (mesmo ponto de entrada).
- **T5 — LGPD de dados sensíveis em repouso.** 29.3 R5 (mensagens clínicas em texto claro) · 29.6 C2 (CPF sem máscara) · 29.4 (citações/retenção) · 29.5 (retenção tabelas SCC).
- **T6 — Prontidão regulatória (prazo externo 04/08/2026).** 29.5 C2/F8.1 (textos RDCs — dependência compartilhada) · 29.2 REG-1..8 · 29.4 (RAG regulatório).
- **T7 — Safety Clamp / segurança de prescrição.** 29.2 C3 (THC não clampado) · 29.4 (estender clamp ao texto do relatório).
- **T8 — Integridade e confiança da trilha (backup/observabilidade).** 29.5 A8 / BUG-001 · 29.1 A2 (métricas voláteis) · heartbeat de jobs (29.6/29.5).
- **T9 — Conciliação e integridade financeira.** 29.6 C1/C3/A1.
- **T10 — Dívida de frontend (dupla superfície + a11y + contrato).** 29.7 C1/A1/A2.

---

## 4. Grafo de dependências (a espinha do cronograma)

```text
                 ┌─────────────────────────────────────────────┐
                 │  INFRA-1  Provisionar Redis + worker RQ      │  ← CHAVE-DE-ABÓBADA
                 │           (29.1 R3-fase1)                    │
                 └───────────────┬─────────────────────────────┘
                                 │ destrava (cutovers na Onda 2)
        ┌────────────────┬───────┼────────────────┬──────────────┬───────────────┐
        ▼                ▼       ▼                ▼              ▼               ▼
  Pipeline IA      Webhook→fila  SLA clínico   Lembretes     Âncora cron     Jobs $
  assíncrono       (29.3 RM3)    (29.2 sp2)    24h/1h        (29.5 R7)       fatura/exp.
  (29.4 R4)                                    (29.2 R7)                     (29.6 R4/R8)

  ┌─────────────────────────┐      ┌─────────────────────────────┐
  │ TEN-1 FKs eixo tenant    │      │ SCC-1 Textos RDCs no RAG     │ ← dependência
  │ (29.1 R2)  [Onda 1]      │      │ (29.5 F8.1)  [Onda 1]        │   compartilhada
  └───────────┬─────────────┘      └──────────┬──────────────────┘
              │ fundação de                    │ destrava
              ▼                                ▼
   TEN-3 RBAC tenant-aware           29.2 REG-5 (legislação) + REG-1..8
   (29.1 R1) [Onda 2]                + RAG regulatório (29.4) [Onda 2]
              │
              ▼
   TEN-5 migra clinic_id→tenant_id (29.1 R4) [Onda 3]  ←reconciliar→  29.2 (tabelas clínicas)
              │
              ▼
   TEN-6 profissional multi-tenant (29.1 F1) [Onda 3]  + filtro LGPD cross-tenant (INV-4)

  COM-3 tenant por phone_number_id (29.3 RM5) [Onda 1]  — independe do RBAC profundo
  PSP Pix dinâmico (29.6 R5) [Onda 2]  — depende de INFRA-1 (webhook real) + TEN-1 (FKs)
```

**Leitura:** INFRA-1, TEN-1 e SCC-1 são as três raízes. Quase tudo de valor na Onda 2 pende de uma delas. Por isso as três abrem a Onda 1.

---

## 5. As três ondas

Datas-alvo (a partir de 2026-06-10): **Onda 1 → ~10/07** · **Onda 2 → ~09/08** · **Onda 3 → ~08/09**.
Esforço: **P** (≤1 dia–2 dias) · **M** (2–5 dias) · **G** (>1 sprint). Prioridade clínica/segurança em **P0/P1**.

### 🌊 Onda 1 (0–30 dias) — Fundação + estancar perdas
*Tema: ligar a chave-de-abóbada, parar perda de dados e vazamento cross-tenant, fechar os itens baratos de prazo externo. Risco baixo, valor alto.*

| ID | Item | Fonte | Esforço | Prior. |
|----|------|-------|---------|--------|
| **INFRA-1** | Provisionar Redis + `rq worker cannabia-ai` no `render.yaml` (sem trocar call-sites ainda; validar infra em prod) | 29.1 R3-f1 | M | P0 |
| **TEN-1** | FKs do eixo tenant: `clinics.tenant_id→tenants`, `user_tenant_roles.user_id→users`/`.tenant_id→tenants`, com limpeza de órfãos + down-migration | 29.1 R2 | P | P0 |
| **TEN-2** | Discriminador de tenant extensível (CHECK literal → validação via `tenant_types`) — destrava tipos futuros sem migration | 29.1 R5 | P | P1 |
| **COM-1** | Idempotência inbound por `wamid` (migration + índice único + `ON CONFLICT DO NOTHING` + curto-circuito) | 29.3 #1 | P | P0 |
| **COM-2** | Loop completo de `entries[]/changes[]/messages[]` no parser do webhook (fim da perda em batch) | 29.3 #2 | P | P0 |
| **COM-3** | Resolução de tenant por `phone_number_id` + HMAC por tenant + propagar `tenant_id` no outbound (fim do vazamento cross-tenant) | 29.3 #3 | M | P0 |
| **CLI-1** | Religar o loop de follow-up no webhook (parar de descartar respostas de pacientes) | 29.2 R1 | P | P0 |
| **CLI-2** | Clamp de THC no Safety Clamp (`max_thc_daily_mg` deixa de ser decorativo) | 29.2 R2 | P | P0 |
| **CLI-3** | `check_anvisa` no caminho de emissão de prescrição | 29.2 R3 | P | P1 |
| **IA-1** | Migrar Gemini 1.5→2.5 Flash + entrada em `MODEL_PRICING` + teste de schema JSON (deadline jun/2026 **já vencido**) | 29.4 #2/#3 | P | P0 |
| **IA-2** | Entrada governada única nos canais do paciente: WhatsApp+Triagem via `process_patient_case`/wrapper (guardrails+billing+audit) | 29.4 #1 | M | P0 |
| **SCC-1** | Textos oficiais das RDCs de 03/02/2026 no repo (`data/legislation/`) + ingestão no RAG — **dependência compartilhada** (destrava 29.2 REG-5 e RAG regulatório) | 29.5 F8.1 | P | P0 |
| **SCC-2** | Monitor do edital do sandbox (reusar `knowledge_monitors`) + responsável nomeado + checklist vivo | 29.5 F8.4/5 | P | P1 |
| **FIN-1** | Validação de valor na conciliação (underpayment deixa de quitar a cobrança) | 29.6 R1 | P | P0 |
| **FIN-2** | LGPD do trilho de pagamento: mascarar `payer_document` + retenção de `raw_payload`/`payment_webhook_log` | 29.6 R2 | P | P0 |
| **OBS-1** | Causa-raiz do BUG-001 (dumps zerados) + verificação tripla automática de backups | 29.5 R12 / MEMORY | M | P0 |
| **FE-1** | Quick wins de a11y: `aria-hidden` default no `MaterialIcon` (347 usos) + skip-link + `aria-current` | 29.7 FE-02 | P | P1 |
| **FE-2** | CI do frontend (`npm ci`+lint+format:check+build em PR) + política de versionamento documentada | 29.7 FE-03 | P | P1 |

**Saída da Onda 1:** infra de fila provada; zero perda de dados conhecida no canal; zero vazamento cross-tenant no webhook; modelo Gemini saneado; canais do paciente auditados/cobrados; textos das RDCs no RAG; backup confiável. **Toda mudança de schema com down-migration e rito `schema_migrations` (29.G).**

### 🌊 Onda 2 (30–60 dias) — Assíncrono real, tenant-aware, prontidão regulatória
*Tema: fazer os cutovers que a Onda 1 destravou; tornar o RBAC tenant-aware; aterrissar a prontidão regulatória clínica antes da vigência 04/08. Risco médio.*

| ID | Item | Fonte | Esforço | Dep. |
|----|------|-------|---------|------|
| **INFRA-2** | Cutover do pipeline de IA para assíncrono: `flow.run()` inline → `enqueue_ai_task` + polling/notificação | 29.4 R4 / 29.1 R3-f2 / 29.3 RM3 | G | INFRA-1 |
| **COM-4** | Resiliência outbound: job de recuperação de sessões presas em `processing`; retry+status-check; processar `value.statuses` | 29.3 #4/#5/#6 | M | INFRA-1 |
| **TEN-3** | RBAC tenant-aware: `get_user_membership`/`get_effective_roles` passam a ler `user_tenant_roles` | 29.1 R1 | G | TEN-1 |
| **CLI-4** | `clinical_alerts` + classificação determinística + fila clínica unificada + job de SLA 15-min | 29.2 sprint 2 | M | INFRA-1 |
| **REG-CLÍNICO** | Bloco de prontidão regulatória clínica REG-1..8 (via inalatória/dermatológica condicionada; protocolos por via; campo condição grave/paliativo; THC>0,2% condicionado; prompts/relatório por tenant) | 29.2 REG-1..8 | M (bloco) | SCC-1 |
| **IA-3** | Governança RAG: sanitização/classificação de chunks na ingestão (anti-injeção indireta) + campos de curadoria + citações persistidas por execução | 29.4 #4/#5/#6/#7 | M | — |
| **FIN-3** | Fluxo Pix ponta-a-ponta na jornada (Sprint F1 do 29.6): `pix_key` por tenant, gancho na confirmação de consulta, QR via WhatsApp, **integração PSP nº1 (Mercado Pago/Efí) com webhook real**, expiração, recibo | 29.6 Sprint F1 | G | INFRA-1, TEN-1 |
| **LGPD-1** | Retenção/criptografia de mensagens clínicas (`whatsapp_sessions.data`) + consentimento no gatilho da anamnese | 29.3 #9 | M | — |
| **COM-5** | Campanhas: corrigir bug `clinic_name`, propagar `tenant_id` no envio, filtro opt-out LGPD em `_resolve_recipients` | 29.3 #10 | P | TEN-3 |

**Saída da Onda 2:** pipeline de IA fora do request; tenancy com papéis reais por tenant; **prontidão regulatória clínica em produção antes de 04/08/2026**; primeiro PSP Pix dinâmico recebendo via webhook; mensagens clínicas cifradas em repouso.

### 🌊 Onda 3 (60–90 dias) — Migração transacional, profundidade, expansão controlada
*Tema: a migração estrutural de tenancy, os módulos que destravam o checklist do sandbox, billing SaaS e a dívida de frontend. Risco alto, faseado.*

| ID | Item | Fonte | Esforço |
|----|------|-------|---------|
| **TEN-4** | Seleção de tenant na sessão: `active_tenant_id` primário + endpoint de switch | 29.1 R7 | M |
| **TEN-5** | Migração de isolamento clínico `clinic_id`→`tenant_id` em ondas por tabela (add col → backfill → FK → dual-predicate → cutover) — **reconciliar com 29.2** | 29.1 R4 | G |
| **TEN-6** | Modelo de vínculo profissional multi-tenant (`professional_tenant_links`) + **filtro obrigatório de tenant ativo em toda query clínica** (pré-condição LGPD, INV-4) | 29.1 F1 | G |
| **SCC-3** | Rastreabilidade — camada de aplicação completa (`traceability_repository/service/blueprint` + leitura pública por QR) — maior bloco restante; **gate do checklist sandbox** | 29.5 F2.6/7/9 | G |
| **SCC-4** | Member Registry + Dispensation Flow (3 bloqueios do Art. 17) + SOPs operáveis + captura de evento adverso via WhatsApp | 29.5 F2.10/11/8, F3.9 | G |
| **SCC-5** | Primeira âncora real em blockchain (deploy `SandboxAnchor.sol` Amoy + clients OTS/Polygon + cron) — decisão humana: wallet/gas | 29.5 F5.8 | M |
| **FIN-4** | Billing SaaS mínimo (Sprint F2 do 29.6): `billing_invoices` + job de ciclo + dunning + página de assinatura/consumo + unificar fonte de receita dos dashboards | 29.6 Sprint F2 | G |
| **IA-4** | Versionamento da base (reativar migration 009) + eval harness (golden set + rubrica) + console de curadoria + painel de fontes no app médico | 29.4 #8/#12/#13 | G |
| **CLI-5** | Jornada clínica completa: documentos/exames (mídia WhatsApp + upload), agenda com médico + lembretes, lista de problemas clínicos | 29.2 sprint 3 | G |
| **FE-3** | Dívida de frontend: decomissionar UI Jinja (redirects Flask→Next), mover `/atendimentos/[id]` para shell novo, design system mínimo, decisão de realtime, navegação evolutiva por `modules` | 29.7 FE-01/05/06/08/10/11 | G |

**Saída da Onda 3:** tenancy transacionalmente migrado; profissional multi-tenant habilitado com isolamento LGPD; SCC operável ponta-a-ponta (rastrear/dispensar/notificar) com âncora real; billing SaaS cobrando; frontend com superfície única. **Fim da remediação → porta da expansão (Onda 2 do programa: hubs novos) se abre.**

---

## 6. Riscos de cronograma e gates externos

| Risco | Natureza | Mitigação no plano |
|-------|----------|--------------------|
| **Vigência das RDCs em 04/08/2026** (~55 dias) | Externo, data fixa | REG-CLÍNICO front-loaded na Onda 2; SCC-1 (textos) na Onda 1. Se a Onda 1 atrasar, SCC-1 e CLI-2/IA-1 têm prioridade absoluta. |
| **Edital do sandbox sem data** | Externo, gatilho imprevisível | SCC-2 (monitor + responsável) na Onda 1. **Risco residual:** o checklist só fica majoritariamente PRONTO após SCC-3/4 (Onda 3); se o edital sair antes, submete-se com gaps assumidos e linguagem de prontidão. |
| **INFRA-1 escorrega** | Interno, chave-de-abóbada | É o primeiro item da Onda 1. Todo o valor da Onda 2 (5 hubs) está atrás dele — não pode deslizar. |
| **BUG-001 sem causa-raiz** | Interno, confiança da trilha | OBS-1 é P0 na Onda 1; trilha regulatória imutável sem backup confiável é inaceitável para auditoria. |
| **Modelo Gemini desligado pelo Google** | Externo, deadline jun/2026 vencido | IA-1 é P0 na Onda 1; hoje já em risco de fallback silencioso. |
| **Definições comerciais pendentes** (doc 05 §15: valores de plano, "paciente ativo", inadimplência) | Decisão de negócio | Gate de negócio antes de FIN-4 (Onda 3); engenharia entrega parametrizada. |

---

## 7. Fora de escopo desta remediação (registrado para não vazar)

- **Hubs novos** (Agro/seed-to-sale, Jurídico, Farmácia de manipulação, Pesquisa/RWD) — Onda 2 do programa, só pós-remediação (MEMORIA_VIVA §5/§7).
- **Extensão seed-to-sale para cultivo** — fase futura planejada; o SCC desta remediação cobre associação audit-ready, não cultivo (29.5 §5 nota).
- **Split de marketplace / modelos de receita de expansão** — decisão estratégica em outro fórum (29.6 limite de escopo).
- **Ecossistema tokenizado (série 28)** e documentos confidenciais (28.12, Mozondó) — fora de qualquer material de remediação.

---

## 8. Próximos passos

1. **Aprovação deste plano por Andre** (mergear o PR da consolidação).
2. Converter a Onda 1 em sprint executável (tracks por hub, mantendo o rito 29.G: 1 track = 1 branch = 1 PR, merge só por Andre).
3. Atualizar `docs/MEMORIA_VIVA.md` com o marco "Onda 1 de mergulhos concluída + doc 30 aprovado" (changelog incrementado — governança §9, prerrogativa do Estrategista).
4. Iniciar a execução por **INFRA-1 + TEN-1 + SCC-1** (as três raízes do grafo §4).

> Reconciliação concluída: os 6 backlogs de hub foram sequenciados contra o alicerce 29.1 sem conflito residual. Onde dois hubs tocavam o mesmo eixo (tenant, fila, RDCs), a dependência foi explicitada (§2/§4) e a ordem resolvida (§5).

*Fim do documento 30. Este é o gate entre diagnóstico e implementação: nenhuma linha de remediação começa antes da aprovação dele.*
