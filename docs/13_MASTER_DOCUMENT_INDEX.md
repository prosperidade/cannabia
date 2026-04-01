# 13 — Índice Mestre da Documentação

## 1. Propósito do documento

Este documento organiza o **índice mestre da documentação principal da CannabIA**, consolidando a ordem oficial dos documentos, o propósito de cada um, a relação entre eles e a sequência recomendada de leitura por perfil.

---

## 2. Premissa de leitura do índice

A documentação da CannabIA deve ser interpretada como documentação de uma **plataforma já existente** que:

- Já possui implementação relevante
- Já passou por reestruturação e refatoração
- Está em processo de consolidação
- Será adaptada para um modelo mais amplo e maduro

Os documentos combinam: leitura do estado atual + definição de produto + definição arquitetural + modelagem de domínio + análise de gaps + roadmap de adaptação.

---

## 3. Estrutura em quatro blocos

| Bloco | Documentos | Foco |
|-------|-----------|------|
| **Contexto e fundação** | 00, 01 | Estado atual, visão de produto, fundamentos |
| **Funcional e estrutural** | 02, 03, 04, 05, 06 | Entidades, jornadas, acompanhamento, white-label, IA |
| **Técnico e arquitetural** | 07, 08, 09, 10 | Arquitetura, banco, integrações, segurança |
| **Transição e execução** | 11, 12, 13, 14 | Gaps, roadmap, índice, encerramento |

---

## 4. Documentos e seus propósitos

### 00 — Estado Atual, Reestruturação e Adaptação
Registra que a plataforma já existe, já foi refatorada e está sendo reorganizada. **Ponto de partida obrigatório.**

### 01 — Fundação de Produto e Negócio
Consolida visão de produto, proposta de valor, objetivo central e base de negócio.

### 02 — Entidades do Ecossistema e Permissões
Define organização-mãe, tenants, entidades, perfis e permissões.

### 03 — Jornadas do Paciente e do Médico
Formaliza a jornada ponta a ponta de ambos os atores centrais.

### 04 — Acompanhamento do Paciente e Alertas
Define questionários, classificação de severidade, alertas e escalonamento.

### 05 — Modelo White-Label e Monetização
Consolida modelo white-label, configuração por tenant e estratégia comercial.

### 06 — Arquitetura de IA, RAG e Conhecimento
Define papel da IA, banco vetorial, fontes de conhecimento e governança.

### 07 — Arquitetura da Plataforma
Consolida arquitetura lógica, módulos e princípios de evolução.

### 08 — Modelo de Domínio e Banco de Dados
Adapta o modelo de dados da base atual para o novo desenho da plataforma.

### 09 — Integrações e Serviços Externos
Organiza integrações externas (WhatsApp, e-mail, pagamentos, PubMed, IA, storage).

### 10 — Segurança, Compliance e Auditoria
Consolida segurança, LGPD, auditoria e governança de acesso.

### 11 — Análise de Lacunas de Implementação
Registra as lacunas entre sistema atual e plataforma aprovada.

### 12 — Roadmap de Adaptação e Refatoração
Transforma as lacunas em fases, prioridades e sequência de execução.

### 13 — Índice Mestre da Documentação
Este documento — referência de navegação da documentação completa.

### 14 — Encerramento da Fase 1 e Critérios de Prontidão
Formaliza o encerramento desta fase e define condições de entrada na próxima.

---

## 5. Sequência recomendada por perfil

### Para fundadores e decisão estratégica
```
00 → 01 → 05 → 11 → 12 → 14
```

### Para arquitetura e tecnologia
```
00 → 02 → 06 → 07 → 08 → 09 → 10 → 11 → 12
```

### Para produto e operação
```
00 → 01 → 02 → 03 → 04 → 05 → 11 → 12
```

### Para implementação técnica
```
00 → 07 → 08 → 09 → 10 → 11 → 12
```

---

## 6. Como interpretar os documentos

Cada documento deve ser lido sob quatro lentes:

| Lente | Pergunta |
|-------|---------|
| **Estado atual implementado** | O que já existe concretamente no sistema? |
| **Estado atual reestruturado** | O que já foi melhorado/refatorado? |
| **Adaptação necessária** | O que precisa mudar para aderir ao novo desenho? |
| **Direção futura** | Como o componente deve funcionar na plataforma consolidada? |

---

## 7. O que esta fase documental encerra

Ao concluir este conjunto, a CannabIA passa a ter formalmente:

- ✅ Contexto claro do estado atual
- ✅ Visão de negócio e proposta de valor
- ✅ Estrutura de ecossistema e permissões
- ✅ Jornadas definidas (paciente e médico)
- ✅ Modelo de acompanhamento
- ✅ Modelo white-label e monetização
- ✅ Visão de IA e conhecimento
- ✅ Arquitetura lógica
- ✅ Direção de banco de dados
- ✅ Arquitetura de integrações
- ✅ Base de segurança e compliance
- ✅ Leitura de gaps
- ✅ Roadmap de adaptação

---

## 8. O que vem depois desta fase

| Caminho | Descrição |
|---------|-----------|
| **Revisão fina** | Ajustes de linguagem e inserção de detalhes mais aderentes ao sistema atual |
| **Documentação operacional** | Publicação em repositório, wiki ou docs folder oficial |
| **Documentação técnica por módulo** | Módulo de pagamentos, questionários, prontuário, PubMed, motor de alertas, migração de tenancy |

---

## 9. Conclusão

A CannabIA agora possui uma **espinha dorsal documental clara, organizada e coerente** com sua realidade técnica e com sua ambição de produto.

Este índice formaliza essa estrutura e é a referência principal de navegação para qualquer pessoa que precise entender, revisar, adaptar ou evoluir a plataforma.
