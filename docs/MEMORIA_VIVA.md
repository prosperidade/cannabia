# MEMÓRIA VIVA — CannabIA × Claude (Programa de Mergulhos)
**Versão:** v1.0 | **Atualizada em:** 10/06/2026
**Função:** documento de continuidade. Ao abrir um chat novo, cole este documento (ou anexe-o) na primeira mensagem. Ele substitui o contexto acumulado do chat anterior.
**Regra de atualização:** a cada marco (decisão tomada, documento aprovado, mergulho concluído), Claude gera nova versão com changelog. A versão canônica vive no repositório em `docs/MEMORIA_VIVA.md`; a cópia do chat é espelho.

---

## 1. O que é a CannabIA (resumo de 1 minuto)

SaaS white-label multi-tenant para o ecossistema brasileiro de cannabis medicinal: anamnese assistida por IA via WhatsApp, prontuário/timeline, agenda, RAG científico (PubMed/ChromaDB), Rules Engine/Safety Clamp para lógica determinística de prescrição, e SCC (Sandbox Compliance Core) — módulo transversal de compliance com rastreabilidade, farmacovigilância e ancoragem blockchain (OpenTimestamps/Bitcoin + Polygon).

**Missão:** democratizar acesso e distribuir riqueza na cadeia, em oposição à concentração de capital dos grandes players.

**Stack:** Flask 3.x + PostgreSQL + Next.js App Router + WhatsApp Business API v22 + OpenAI/Gemini + ChromaDB. Deploy: Render (1 worker eventlet — gargalo conhecido).

**Estrutura societária aprovada (série 28, v1.0 consolidada):** PJ-1 Holding SA (ativos estratégicos) · PJ-2 Investimentos SA (CVM 88, Fundo Comunitário, Caminho B + golden share) · PJ-3 Instituto OSCIP (10% Class B na PJ-1) · PJ-4 federação de associações a convidar (FACT como candidata natural — convite, não fato consumado) · PJ-5 SPEs. Tokens: $CANA (missão, PJ-3) e token do Fundo (security, PJ-2). Confidencial fora de docs públicos: doc 28.12 (CPR-F tokenizada Ano 2) e Fazenda Mozondó.

---

## 2. Marco regulatório vigente (driver de tudo)

- **03/02/2026:** Anvisa publica no DOU as RDCs do novo marco — cultivo por PJs com rastreabilidade obrigatória; RDC 1.012/2026 (pesquisa); RDC 1.014/2026 (associações + sandbox regulatório, implementação depende de EDITAL ainda sem data); canabidiol em farmácias de manipulação; novas vias de administração; THC >0,2% para condições graves.
- **04/08/2026:** vigência das RDCs. **Único prazo externo do programa.**
- Mercado: ~873 mil pacientes, ~315 associações (47 com avanço judicial para cultivo), projeção R$ 1 bi em 2026.

---

## 3. Estado do sistema (auditoria abr/2026 + doc 17)

| Hub | Maturidade | Síntese |
|---|---|---|
| Clínico | 🟡 | Anamnese/agenda/atendimentos operantes; prontuário longitudinal parcial |
| Comunicação (WhatsApp) | 🟢 | Mais maduro; síncrono, máquina de estados hardcoded p/ anamnese |
| IA & Conhecimento | 🟡 | Pipeline 3 etapas c/ auditoria de custo; governança RAG incompleta; antiinjeção por regex |
| Compliance/SCC | 🟡 | Docs 22–26 prontos; migrations renumeradas 024–036; implementação inicial; BACKLOG_SCC.md incompleto |
| Tenancy/Plataforma | 🟠 | Fase de fundação aditiva (doc 17): tenant_id convive com clinic_id; migration 004; user_tenant_roles; RBAC completo pendente. 1 worker, sem fila assíncrona, migrations sem versionamento |
| Financeiro | 🔴 | Migration 021 (Pix EMV) existe; jornada não integrada; billing ausente |
| Frontend | 🟠 | Migração Jinja→Next.js em curso; 5 rotas no ar; sem design system; deps "latest" |

**Veredicto da auditoria:** apto para operação controlada; NÃO pronto para uso intensivo sem hardening (resiliência, integridade, assíncrono, observabilidade, governança transversal).

---

## 4. Decisões tomadas (log)

| Data | Decisão |
|---|---|
| ~abr/2026 | Migrations SCC renumeradas 024–036; recomendação Opção B (blueprints por submódulo, compliance.py como fachada) — HANDOFF_VALIDATION_REPORT |
| 10/06/2026 | **Ordem travada: diagnóstico → remediação → expansão.** Nenhuma feature nova antes do plano de remediação consolidado |
| 10/06/2026 | Programa de Mergulhos aprovado (doc 29): Onda 0 (decisão), Onda 1 (7 diagnósticos), Onda 2 (3 hubs novos) |
| 10/06/2026 | Onda 1 roda em PARALELO (sessões read-only, sem conflito); prompts de handoff prontos (doc 29.0) |
| 10/06/2026 | CannabIA NÃO venderá sementes/insumos diretamente — infraestrutura e curadoria, nunca vendedor (risco regulatório + P1) |
| 10/06/2026 | Farmácia de manipulação aprovada como futuro TIPO DE TENANT (não "mais um login") — descoberta no Mergulho 10, implementação só pós-remediação |
| 10/06/2026 | Checklist de submissão ao sandbox (Mergulho 5, item 4) = prioridade máxima da Onda 1 (prazo externo) |
| 10/06/2026 | Memória Viva + Governança Documental instituídas (este doc + doc 29.G) |

---

## 5. Registro documental (série atual)

| Doc | Conteúdo | Status |
|---|---|---|
| 21 / auditoriasistema1.md | Auditoria completa do sistema (abr/2026) | ✅ Referência |
| 22–26 | SCC: arquitetura, piloto, modelo de dados, ancoragem, templates | ✅ Aprovados |
| 28.A, 28.B, 28.0, 28.1 | Ecossistema tokenizado — Versão Consolidada v1.0 | ✅ Aprovados, prontos p/ parceiros |
| 28.12 | CONFIDENCIAL: CVM Sandbox / CPR-F Ano 2 | 🔒 Interno |
| 29 | Programa de Mergulhos por Hub (v0.1→v1.0 com ordem travada) | ✅ Aprovado |
| 29.0 | Prompts de handoff Onda 1 (7 sessões paralelas) | ✅ Entregue |
| 29.G | Governança documental e Git do programa | ✅ Entregue (10/06) |
| 29.1–29.7 | Relatórios dos mergulhos (Desktop) | ⬜ Aguardando execução |
| BACKLOG_SCC.md | Backlog SCC | 🟡 Incompleto — completar no Mergulho 5 |
| 30 | Plano de Remediação Consolidado | ⬜ Futuro (pós-Onda 1, sessão web) |
| Mergulho 0 | Taxonomia de hubs + modelo de negócio | ⬜ Pendente (web, pré-Onda 2) |
| Mergulhos 8–10 | Hubs novos: Agro, Jurídico, Farmácias+Pesquisa | ⬜ Só após remediação |

---

## 6. Oportunidades mapeadas (ainda não decididas)

1. **Seed-to-sale como produto âncora** — rastreabilidade obrigatória por RDC = demanda compulsória; SCC é ~70% do caminho; inverte a ordem de venda (cultivador entra pela rastreabilidade, depois consome rede de profissionais).
2. **Farmácias de manipulação** como tipo de tenant — possivelmente o maior TAM novo; produto atual cobre ~60-70% da dor.
3. **RWD para pesquisa (RDC 1.012)** — licenciamento de dados via PJ-1, missão via PJ-3.
4. **Hub Agro ↔ 28.12** — cultivadores rastreados on-chain = originação ideal de CPR-F tokenizada (nota interna, fora de docs públicos).
5. Hubs de profissionais (agrônomos, advogados) = modelo marketplace — depende da decisão de taxonomia (Mergulho 0).

---

## 7. Próximas ações (na ordem)

1. Rodar os 7 mergulhos no Claude Desktop (prompts no doc 29.0; governança no 29.G). Levas sugeridas: A = 1, 5, 4 · B = 2, 3, 6, 7.
2. Sessão de consolidação na web → doc 30 (Plano de Remediação Consolidado).
3. Executar remediação em ondas (30/60/90).
4. Mergulho 0 (taxonomia/modelo de negócio) — pode rodar na web em paralelo à remediação.
5. Onda 2 (hubs novos) somente após remediação.
6. Monitorar publicação do edital do sandbox Anvisa (gatilho externo que fura fila).

---

## 8. Princípios e invariantes (nunca violar)

- P1–P9 invioláveis; em especial P1 (autonomia de clínicas/associações/médicos — estímulos legítimos só no perímetro próprio).
- Prontidão regulatória ≠ aprovação regulatória (aprovar é prerrogativa da Anvisa) — em toda comunicação.
- Invariantes hardcoded (rastreabilidade, farmacovigilância, LGPD) nunca são tenant-configuráveis (Art. 17).
- Blockchain = âncora, não banco operacional (PostgreSQL append-only + hash chaining + ancoragem pública).
- Documento fundacional aprovado ANTES de documentos downstream.
- Federação (FACT) = parceira a convidar, nunca "incorporada".
- Mozondó e 28.12 fora de qualquer material público.

---

## Changelog

- **v1.0 (10/06/2026):** versão inicial. Consolida estado pós-aprovação do Programa de Mergulhos, ordem diagnóstico→remediação→expansão, prompts da Onda 1 e instituição da governança documental.
