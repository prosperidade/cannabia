# 21 — Auditoria Completa do Sistema (2026-04-03)

## 1) Escopo da auditoria

Esta auditoria cobre a base atual da CannabIA com foco em:

- arquitetura geral (backend, frontend, dados, integrações)
- banco de dados e migrations
- segurança, governança e observabilidade
- funcionalidades implementadas vs. lacunas
- agentes/fluxos de IA e riscos de operação
- UX/UI e estratégia de evolução
- operacionalidade, resiliência e prontidão para uso intensivo
- capacidade offline e recomendações práticas

A análise foi feita por leitura técnica do código e documentos oficiais do repositório.

---

## 2) Resumo executivo

### Maturidade atual (nota qualitativa)

- **Base funcional:** boa para operação inicial e evolução incremental.
- **Prontidão para escala intensa:** **ainda insuficiente** sem reforços em infraestrutura, banco e controles operacionais.
- **Risco principal:** crescimento de carga sobre arquitetura ainda “foundation” em várias áreas (tenancy ampliado, finance/billing, monitoramento e governança transversal).

### Diagnóstico objetivo

1. **Pontos fortes reais**
   - Backend Flask modular com app factory, blueprints e API v1 padronizada.
   - Pipeline de IA funcional com auditoria de execução e custo.
   - Fundação de tenancy ampliado (`tenant_id`) já iniciada e convivendo com `clinic_id`.
   - Frontend Next.js em produção de migração, reduzindo dependência de Jinja.

2. **Gargalos de alto impacto**
   - Modelo de dados ainda com baixa densidade de constraints/fks nas tabelas legadas.
   - Migrações sem trilha de versão aplicada no banco (idempotência via `IF NOT EXISTS`, sem tabela de controle).
   - Arquitetura de runtime com 1 worker eventlet no deploy de referência (alto risco sob pico).
   - Ausência de estratégia formal de filas, retries assíncronos e circuit breaker para integrações externas.

3. **Conclusão executiva**
   - O sistema **está apto para operação controlada e crescimento gradual**, mas **não está pronto para uso intensivo massivo** sem um ciclo de hardening técnico e operacional em ondas de 30/60/90 dias.

---

## 3) Auditoria por camada

## 3.1 Backend

### Situação atual

- Aplicação Flask centralizada em `create_app`, com autenticação via Flask-Login, contexto de tenancy por request, blueprints e logging por request.
- API v1 apresenta envelope consistente (`data/meta/error`), paginação, CSRF em endpoints mutáveis e normalização de serialização.

### Riscos e limitações

- Mistura transitória entre rotas legacy (templates) e API moderna: aumenta superfície de manutenção.
- Tenancy efetivo ainda nasce de `clinic_id` e só depois projeta `tenant_id` (modelo híbrido ainda em transição).
- Sem camada clara de jobs assíncronos para operações demoradas (IA/integradores).

### Recomendações

- Consolidar padrão “backend as API first” para todo novo módulo.
- Introduzir fila (Celery/RQ/Cloud task queue) para IA, notificações e integrações.
- Definir contrato de timeout, retry, idempotência e dead-letter para serviços externos.

---

## 3.2 Banco de dados e migrations

### Situação atual

- Base cresce por SQL sequencial (`001` a `006`) com expansão para tenant, timeline e prontuário.
- Há entidades relevantes para operação clínica e IA.

### Pontos críticos encontrados

1. **Legado sem FKs robustas em parte do schema inicial**
   - O próprio `001_initial_schema.sql` explicita decisão de evitar FKs em tabelas-base.
   - Impacto: risco de inconsistência referencial silenciosa sob carga e integrações concorrentes.

2. **Modelo de migrations sem tabela de versionamento aplicado**
   - O runner executa todos os arquivos em ordem e depende de comandos idempotentes.
   - Impacto: baixa rastreabilidade de drift entre ambientes.

3. **Índices parciais para escala futura**
   - Há índices úteis em módulos novos (timeline/prontuário), mas ainda faltam índices orientados aos filtros mais frequentes de operação e auditoria em produção.

4. **Dados sensíveis em configurações de integração por tenant**
   - Estruturas com campos `_encrypted` existem no schema, porém sem política criptográfica operacional explicitada no código auditado.

### Recomendações

- Adotar framework/versionamento de migrations com tabela de histórico (ou criar tabela de controle própria).
- Planejar “hardening de integridade” por ondas: FKs, constraints, checks e políticas de deleção.
- Revisar estratégia de índices com base em telemetria real de queries (p95/p99).
- Formalizar criptografia de segredos em repouso (KMS/Envelope encryption) + rotação.

---

## 3.3 Frontend e UX

### Situação atual

- Estratégia oficial de migração para Next.js está correta e já em execução.
- Frontend novo já consome API v1 com sessão/cookie e rotas operacionais iniciais.

### Diagnóstico UX/UI

- **Acerto:** decisão de não investir pesado no legado Jinja.
- **Lacuna:** ausência de design system formal, padrões de acessibilidade e telemetria de comportamento do usuário.
- **Risco:** dependência de “latest” em dependências do frontend reduz previsibilidade de build/release.

### Recomendações de UI/UX

- Criar design system mínimo (tokens, tipografia, espaçamento, componentes base).
- Definir guideline de acessibilidade (teclado, contraste, foco, semântica).
- Implantar analytics de produto orientado a jornada clínica (drop-off por etapa).
- Fixar versões de `next/react/react-dom` para estabilidade de release.

---

## 3.4 IA, agentes e governança

### Situação atual

- Pipeline em 3 etapas com fallback entre provedores, validação de payload e auditoria de execução/custos.
- Antiinjeção existe, mas é heurística por regex.
- Visão de “super agente” está documentada como objetivo de produto multicanal (GPT, web e WhatsApp).

### Riscos técnicos

- Dependência de chamadas síncronas para fluxo clínico pode degradar UX em picos.
- Regras antiinjeção baseadas apenas em padrões textuais podem gerar falso negativo.
- Governança de conhecimento/RAG ainda parcial (curadoria, versionamento de base e rastreabilidade científica incompletos).

### Recomendações

- Mover execução de IA pesada para jobs assíncronos com estados de processamento.
- Adotar política de guardrails em camadas: validação sintática + semântica + detecção comportamental.
- Versionar base de conhecimento com trilha de proveniência por documento/chunk.
- Implantar avaliação contínua de qualidade clínica (rubricas e amostragem auditável).

---

## 3.5 Segurança, compliance e auditoria

### Situação atual

- Há CSRF, rate limit básico, hashing de senha e redaction em logs.
- Auditoria de IA está mais madura que auditoria transversal.

### Gaps relevantes

- Falta trilha unificada de auditoria para ações clínicas e administrativas críticas.
- Segregação de papéis ainda em evolução com a migração de tenancy.
- Falta playbook formal para incidentes de segurança e continuidade operacional.

### Recomendações

- Criar trilha de auditoria transversal (quem, o quê, quando, antes/depois).
- Implementar política de privilégio mínimo e revisão periódica de acessos.
- Estruturar programa LGPD operacional (mapa de dados, retenção, descarte, atendimento a titular).
- Definir runbooks de incidente (segurança, banco, provedores de IA, WhatsApp).

---

## 3.6 Operacionalidade e preparação para uso intensivo

### Situação atual

- Deploy de referência no Render com API e frontend separados.
- API configurada com gunicorn + eventlet e **1 worker**.

### Diagnóstico de capacidade

- Configuração atual favorece simplicidade, não throughput alto.
- Falta estratégia explícita de autoscaling, fila e isolamento de workloads críticos.
- Observabilidade ainda insuficiente para SRE (SLO, métricas de saturação, tracing distribuído).

### Recomendações de escala

1. **Curto prazo (0–30 dias)**
   - elevar baseline de concorrência (workers/threads) com teste de carga;
   - instituir health checks funcionais (DB + provider reachability);
   - instrumentar métricas de latência p95/p99 e taxa de erro por endpoint.

2. **Médio prazo (31–60 dias)**
   - introduzir fila assíncrona para IA/integrações;
   - implementar cache para leituras quentes (dashboard/listagens);
   - separar workloads interativos vs. batch.

3. **Estrutural (61–90 dias)**
   - arquitetura resiliente multi-serviço (API, workers, scheduler);
   - plano de capacidade com testes periódicos de estresse;
   - política de DR/backup restaurável com RTO/RPO definidos.

---

## 4) Offline e continuidade de operação

### Estado atual

- Não há arquitetura offline-first observável no frontend.
- Fluxos críticos dependem de serviços externos (IA, WhatsApp, e-mail, banco online).

### Estratégia recomendada

- Implementar modo degradado:
  - fila local temporária de ações do usuário quando integrações falharem;
  - reprocessamento assíncrono com reconciliação.
- Para frontend, avaliar PWA progressivo apenas para casos de consulta e rascunho, com escopo controlado.
- Para operação clínica, priorizar “continuidade sem IA” com fallback manual assistido.

---

## 5) Sugestões de funcionalidades (priorizadas)

## Prioridade A (alto valor + alto risco mitigado)

1. **Fila clínica unificada** (tarefas pendentes de revisão, alerta e follow-up).
2. **Motor de escalonamento de alertas** com SLA e trilha de resolução.
3. **Prontuário longitudinal navegável por problema clínico** (não apenas por evento).
4. **Consolidação de auditoria transversal** (clínica, segurança, financeiro, IA).

## Prioridade B (crescimento do produto)

5. **Domínio de pagamentos/QR Code** integrado à jornada.
6. **Billing multi-tenant** (planos, limites, consumo IA, cobrança recorrente).
7. **Módulo de templates e campanhas de comunicação por tenant**.

## Prioridade C (diferencial competitivo)

8. **Governança científica completa** (PubMed + curadoria + score de evidência).
9. **Copiloto médico com explicabilidade e referências rastreáveis por recomendação**.
10. **Métricas de efetividade clínica e aderência terapêutica por coorte**.

---

## 6) Plano de evolução recomendado

## Fase 1 — Hardening operacional (4 semanas)

- observabilidade, correção de gargalos p95/p99, runbooks e incident response;
- melhorias de integridade e índices no banco;
- estabilização de versões de frontend/backend.

## Fase 2 — Escala funcional (4–8 semanas)

- fila assíncrona de IA e integrações;
- evolução de prontuário, timeline e alertas;
- RBAC/tenancy avançado.

## Fase 3 — Plataforma completa (8–16 semanas)

- financeiro (pagamentos + billing);
- governança científica robusta;
- experiência white-label avançada por tenant.

---

## 7) Conclusão final

A CannabIA tem uma base técnica promissora e já funcional para operação clínica assistida por IA em estágio inicial. O caminho correto não é reconstrução, e sim evolução incremental com disciplina de arquitetura e operação.

Para ficar pronta para uso intensivo, a prioridade deve ser: **resiliência operacional, integridade de dados, desacoplamento assíncrono, observabilidade e governança transversal**. Com este foco, o sistema pode evoluir de um bom foundation para uma plataforma clínica multi-tenant robusta.
