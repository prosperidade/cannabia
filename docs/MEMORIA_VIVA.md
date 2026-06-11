# MEMÓRIA VIVA — CannabIA × Claude (Programa de Mergulhos)
**Versão:** v2.2 | **Atualizada em:** 11/06/2026 (marco: doc 30 v1.2 mergeado na main + faxina de branches concluída)
**Função:** documento de continuidade. Ao abrir um chat novo, anexar este documento na primeira mensagem; Claude assume o contexto a partir dele.
**Cadência:** v2.x a cada marco da remediação; v3.0 ao fim da Onda 3 (porta da expansão). Versão canônica: `docs/MEMORIA_VIVA.md`; a cópia do chat é espelho. Toda atualização incrementa versão e changelog.

---

## 1. O que é a CannabIA (resumo de 1 minuto)

SaaS white-label multi-tenant para o ecossistema brasileiro de cannabis medicinal: anamnese assistida por IA via WhatsApp, prontuário/timeline, agenda, RAG científico (PubMed/ChromaDB), Rules Engine/Safety Clamp para prescrição determinística, e SCC (Sandbox Compliance Core) — módulo transversal de compliance com rastreabilidade, farmacovigilância e ancoragem blockchain (OpenTimestamps/Bitcoin + Polygon).

**Missão:** democratizar acesso e distribuir riqueza na cadeia, em oposição à concentração de capital dos grandes players.

**Stack:** Flask 3.x + PostgreSQL + Next.js App Router (60 páginas, 4 shells por perfil) + WhatsApp Business API v22 + OpenAI/Gemini + ChromaDB + Redis/RQ (provisionamento pendente). Deploy: Render, 2 workers eventlet.

**Estrutura societária (série 28, v1.0 consolidada):** PJ-1 Holding SA · PJ-2 Investimentos SA (CVM 88, Caminho B + golden share) · PJ-3 Instituto OSCIP (10% Class B na PJ-1) · PJ-4 federação a convidar (FACT candidata — convite, não fato consumado) · PJ-5 SPEs. Tokens: $CANA (missão, PJ-3) e token do Fundo (security, PJ-2). 🔒 Confidencial fora de docs públicos: 28.12 (CPR-F Ano 2) e Fazenda Mozondó.

---

## 2. Marco regulatório (driver de tudo)

- **03/02/2026:** RDCs Anvisa no DOU — cultivo por PJs com rastreabilidade obrigatória; RDC 1.012 (pesquisa); RDC 1.014 (associações + sandbox, depende de EDITAL sem data); canabidiol em farmácias de manipulação; novas vias; THC >0,2% p/ condições graves.
- **04/08/2026:** vigência. **Prazo externo fixo — faltam ~55 dias.** O bloco REG-1..8 (29.2) deve estar em produção até ~25/07.
- **Edital do sandbox (FRAMING CORRETO, fixado por Andre em 10/06):** o sandbox da CannabIA é um PRODUTO PRIVADO de prontidão — prepara as associações clientes para concorrerem ao edital. Quem submete e concorre é CADA ASSOCIAÇÃO, por decisão própria (P1); a CannabIA não tem obrigação, compromisso ou prazo com a Anvisa. O edital é gatilho COMERCIAL (pico de demanda pelo plano Sandbox Ready), não deadline de compliance. Monitor do edital (SCC-2) permanece — avisar clientes primeiro é vantagem comercial.
- ⚠️ Os **textos oficiais das RDCs de 2026 NÃO estão no repositório nem no RAG** (29.5 C2) — item SCC-1, primeiro da remediação.

---

## 3. Estado do sistema — VERIFICADO EM CÓDIGO (Onda 1, 10/06/2026, commit base ~76cabe4)

> Substitui a tabela baseada na auditoria de abr/2026, que continha premissas defasadas (1 worker, sem versionamento de migrations, billing ausente, deps "latest" — todas corrigidas pelos mergulhos).

| Hub | Relatório | Síntese verificada |
|---|---|---|
| Tenancy/Plataforma | 29.1 | Fundação tenant ~95% criada, MAS `user_tenant_roles` morta em runtime (RBAC tenant-aware = 0%); duas gerações de schema convivem (clínico legado clinic_id-only × SCC/billing tenant-native); fila RQ completa em código e MORTA (sem Redis no render.yaml, `enqueue_ai_task` sem callers); 2 workers; `schema_migrations` com checksum existe; FKs faltam no eixo tenant (clinics.tenant_id, user_tenant_roles) |
| Clínico | 29.2 | Anamnese/prontuário/atendimentos operantes; **loop de follow-up QUEBRADO** (respostas de pacientes descartadas — C1); **sem motor de alertas/SLA** (C2); **Safety Clamp não aplica max_thc** (C3); jornada comercial desconectada (aceite/pagamento/agenda em ilhas); bloco REG-1..8 mapeado p/ vigência 04/08 |
| Comunicação | 29.3 | Webhook HMAC ok, MAS: sem idempotência por wamid (duplicação no retry da Meta), parser lê só messages[0] (perda em batch), **clinic_id sempre DEFAULT (single-tenant de fato, risco cross-tenant)**, outbound sem retry, recibos de entrega descartados; campanhas EXISTEM (011) mas sem templates HSM (só janela 24h); custo Meta da anamnese ≈ zero |
| IA & Conhecimento | 29.4 | Pipeline real = 4 etapas (Prescritor incluído); guardrails em 4 camadas MAS **WhatsApp+Triagem rodam SEM guardrails/billing/audit** (C1); injeção indireta via RAG sem defesa (C2); **Gemini 1.5 Flash além do prazo de depreciação** (C3); versionamento da base (migration 009) morto; referências do relatório não verificáveis |
| Compliance/SCC | 29.5 | **Série correta: docs 23–27; migrations 024–037.** Governance, farmacovigilância (interna), evidence, reporting = IMPLEMENTADOS; **rastreabilidade e SOPs = schema sem camada de aplicação** (C1); ancoragem completa em MOCK (nenhuma âncora real); VigiMed/Notivisa stubs; 12 templates ativos (só Markdown). **Checklist sandbox: 9 PRONTO / 11 PARCIAL / 10 AUSENTE** — forte em documental/governança, fraco no operacional do Art. 17 |
| Financeiro | 29.6 | TRÊS domínios financeiros desconexos (Pix 021 / billing 010 / legado 014 — dashboards leem o legado!); billing com metering de IA ENFORCED existe desde 010 (premissa "ausente" estava errada); conciliação 100% manual (BR Code estático, sem PSP); sem invoice/dunning/renovação; LGPD: CPF sem máscara em webhook log |
| Frontend | 29.7 | 60 páginas Next em 4 shells; migração 75% MAS **dupla superfície autenticada** (Jinja segue ativo em paralelo); realtime não migrado; 3 linguagens visuais + 2 kits duplicados; a11y regrediu no shell novo (347 ícones lidos por screen reader); zero telemetria de produto; deps com lockfile ok (premissa "latest" errada) |

**Diagnóstico consolidado (doc 30):** apto a operação controlada, não pronto para uso intensivo. **A remediação é mais ATIVAR o que existe do que construir do zero.** A chave-de-abóbada é a fila assíncrona em produção (INFRA-1) — destrava 5 hubs.

---

## 4. Decisões tomadas (log)

| Data | Decisão |
|---|---|
| ~abr/2026 | SCC renumerado docs 23–27 / migrations 024–037; Opção B (blueprints por submódulo) — parcialmente executada |
| 10/06/2026 | Ordem travada: diagnóstico → remediação → expansão. Sem features novas antes do doc 30 executado |
| 10/06/2026 | Programa de Mergulhos (doc 29) + prompts (29.0) + governança 29.G + Memória Viva instituídos |
| 10/06/2026 | CannabIA NUNCA vende sementes/insumos — infraestrutura + curadoria, não vendedor (risco regulatório + P1) |
| 10/06/2026 | Farmácia de manipulação = futuro TIPO DE TENANT; descoberta no Mergulho 10; implementação pós-remediação |
| 10/06/2026 | Execução via agentes no VS Code sob 29.G; docs do programa em `docs/`; mempalace removido do projeto (não citar/sugerir) |
| 10/06/2026 | **Onda 1 EXECUTADA E MERGEADA no mesmo dia**: 7 sessões paralelas, PRs #57–#63 (squash, merge do Andre), BACKLOG_SCC reconciliado, branches limpas, ponteiro 29.G no CLAUDE.md (#64) |
| 10/06/2026 | **Doc 30 v1.0 produzido** (Plano de Remediação Consolidado, 3 ondas 30/60/90). Status: AGUARDANDO aprovação formal do Andre, com 3 ressalvas do estrategista (ver §6) |
| 10/06/2026 | Premissas da auditoria abr/2026 oficialmente superadas — fonte de estado do sistema passa a ser os relatórios 29.1–29.7 |
| 10/06/2026 | **FRAMING CORRIGIDO (Andre):** sandbox CannabIA = produto privado de prontidão; quem concorre ao edital é cada associação (P1); CannabIA sem obrigação/prazo com a Anvisa; edital = gatilho comercial. Doc 30 → v1.1 com a correção. Ressalvas 1 e 2 aceitas; ressalva 3 substituída por template de papéis por associação (doc 27) |
| 10/06/2026 | Faxina de branches em 2 fases: Fase 1 inventário read-only (classes A/B/C); Fase 2 deleção só por decisão do Andre por classe |

---

## 5. Registro documental

| Doc | Conteúdo | Status |
|---|---|---|
| 23–27 | Série SCC (numeração correta) | ✅ Aprovados; implementação parcial mapeada no 29.5 |
| 28.A/B/0/1 | Ecossistema tokenizado v1.0 | ✅ Prontos p/ parceiros |
| 28.12 | 🔒 CVM Sandbox / CPR-F Ano 2 | Interno |
| 29, 29.0, 29.G | Programa, prompts, governança | ✅ Na main |
| **29.1–29.7** | Relatórios diagnósticos da Onda 1 | ✅ **Mergeados (PRs #57–#63)** |
| BACKLOG_SCC.md | Reconciliado pelo Mergulho 5 | ✅ Atualizado |
| **30** | Plano de Remediação Consolidado v1.0 | 🟡 **Aguardando aprovação do Andre** (3 ressalvas em aberto) |
| MEMORIA_VIVA.md | Este documento | 🔄 v2.0 |
| Mergulho 0 | Taxonomia de hubs + modelo de negócio | ⬜ Web, pode rodar em paralelo à remediação |
| Mergulhos 8–10 | Hubs novos (Agro, Jurídico, Farmácias+Pesquisa) | ⬜ Só pós-Onda 3 do doc 30 |

---

## 6. Plano de remediação (doc 30) — síntese + ressalvas do estrategista

**Três raízes que abrem tudo:** INFRA-1 (Redis + worker RQ em produção) · TEN-1 (FKs do eixo tenant) · SCC-1 (textos das RDCs no repo/RAG).

**Onda 1 (até ~10/07):** estancar perdas (idempotência wamid, parser batch, tenant por phone_number_id, religar follow-up, clamp de THC, Gemini 2.5, entrada governada de IA, validação de valor Pix, máscara de CPF, BUG-001 backups) + fundações (FKs, discriminador extensível, monitor do edital).
**Onda 2 (até ~09/08):** cutover assíncrono do pipeline, RBAC tenant-aware, **bloco REG-1..8**, governança RAG, PSP Pix dinâmico, criptografia de mensagens.
**Onda 3 (até ~08/09):** migração clinic_id→tenant_id, profissional multi-tenant (com filtro LGPD obrigatório), rastreabilidade/dispensação/SOPs operáveis, primeira âncora real, billing SaaS, dívida de frontend.

**Ressalvas — DECIDIDAS por Andre em 10/06:**
1. ✅ ACEITA — Colisão de datas: REG-1..8 + IA-2 = primeiro sprint da Onda 2, concluir até ~25/07 (antes da vigência 04/08).
2. ✅ ACEITA — Onda 1 em 4-5 tracks (1 track = 1 branch = PRs pequenos sequenciais) + janela diária de triagem.
3. 🔁 SUBSTITUÍDA — A premissa de "CannabIA como proponente" estava errada (framing corrigido, ver §2). O artefato correto é um **template de papéis de submissão POR ASSOCIAÇÃO** na biblioteca do SCC (doc 27): quem da associação prepara, RT revisa, jurídico assina, quem submete. Item de backlog comum, sem urgência artificial.

**✅ Doc 30 MERGEADO na main (v1.2):** combina o framing v1.1 (edital = gatilho comercial; sujeito da submissão = associação cliente, §1.4 e §6) + **SEC-1** (HTTP security headers — achado da faxina: a main não tinha nenhum). PR #65 (v1.0) fechada; #66 (v1.1) e #68/#69 mergeadas. **Gate diagnóstico→implementação liberado.**

---

## 7. Próximas ações (na ordem)

1. ✅ FEITO — Doc 30 v1.2 mergeado na main (gate liberado).
2. ✅ FEITO — Faxina de branches **Fases 1+2 concluídas**: `docs/FAXINA_BRANCHES.md` na main; repo reduzido a só `main` (50 branches + 5 worktrees removidos); valor da Classe C extraído antes do descarte (doc `sprint_3_SCC_I1.md` com rollback das migrations 022/023; item SEC-1 no doc 30).
3. **PRÓXIMO** — Converter Onda 1 do doc 30 em 4-5 tracks executáveis (rito 29.G; prompts de remediação a gerar na web).
4. Disparar pelas raízes: INFRA-1 + TEN-1 + SCC-1.
5. Template de papéis de submissão por associação → biblioteca SCC (doc 27), backlog comum.
6. Mergulho 0 (taxonomia/modelo de negócio) na web, em paralelo à remediação.
7. Monitor do edital (SCC-2): vigilância comercial — avisar clientes primeiro.

---

## 8. Princípios e invariantes (nunca violar)

- P1–P9; em especial P1 (autonomia de clínicas/associações/médicos).
- Prontidão regulatória ≠ aprovação (Anvisa decide) — em toda comunicação e em todo documento.
- Rastreabilidade, farmacovigilância e LGPD nunca tenant-configuráveis (Art. 17) — invariantes de arquitetura.
- Blockchain = âncora, não banco. **Não alegar "verificável em blockchain pública" até a primeira âncora real (29.5 Anexo D, passo 8).**
- Documento fundacional aprovado antes de downstream. Doc 30 é o gate atual.
- FACT = parceira a convidar. Mozondó e 28.12 fora de material público.
- Governança 29.G: agentes nunca mergeiam nem commitam em main; escrita só no mapa autorizado; pre-flight que aborta.
- Profissional multi-tenant só com filtro de tenant ativo em toda query clínica (INV-4 do doc 30) — pré-condição LGPD.

---

## Changelog

- **v2.2 (11/06/2026):** doc 30 **mergeado na main** (v1.2 = framing v1.1 + SEC-1 security headers). **Faxina de branches Fases 1+2 concluídas:** repo reduzido a só `main` (50 branches + 5 worktrees removidos); valor da Classe C extraído antes do descarte (`docs/sprints/sprint_3_SCC_I1.md` com DOWN/rollback das migrations 022/023; item SEC-1 — a main não definia nenhum HTTP security header). Episódio de colisão de sessões paralelas no mesmo working tree (PR #66 com base errada + commit fora de lugar) recuperado sem perda — **lição registrada: uma sessão de escrita por working tree, ou worktree isolado por sessão.**
- **v2.1 (10/06/2026):** correção de framing fixada por Andre — sandbox CannabIA é produto privado de prontidão; a submissão ao edital é prerrogativa de cada associação; sem obrigação/prazo com a Anvisa; edital = gatilho comercial. Ressalvas do doc 30 decididas (1 e 2 aceitas; 3 substituída por template de papéis por associação). Doc 30 pendente de v1.1. Faxina de branches instituída em 2 fases.
- **v2.0 (10/06/2026):** marco de consolidação. Onda 1 executada e mergeada (PRs #57–#63); estado dos hubs reescrito 100% a partir dos relatórios 29.1–29.7 (substitui auditoria de abr/2026); correções de registro (SCC = docs 23–27; migrations até 037); doc 30 v1.0 registrado como aguardando aprovação com 3 ressalvas; próximas ações reorientadas para a remediação.
- **v1.1 (10/06/2026):** execução via VS Code; localização documental (`docs/`); bootstrap; visão de expansão consolidada.
- **v1.0 (10/06/2026):** versão inicial.
