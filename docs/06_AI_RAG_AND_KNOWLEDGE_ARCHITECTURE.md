# 06 — Arquitetura de IA, RAG e Conhecimento

## 1. Propósito do documento

Este documento define a **arquitetura conceitual de IA, RAG e gestão do conhecimento** da plataforma CannabIA, estabelecendo o papel da inteligência artificial no produto, os limites de atuação, a função do banco vetorial, as fontes de conhecimento previstas e os princípios de governança.

---

## 2. Visão geral

A IA na CannabIA é uma **camada estrutural de apoio operacional, apoio informacional e preparação clínica** — não um fim em si mesma.

**Modelo central:**
> IA como copiloto operacional e clínico-informacional; médico como decisor final.

---

## 3. Princípio central de uso da IA

A IA da CannabIA atua como:
- **Organizadora** — estrutura dados e anamneses
- **Sintetizadora** — resume e consolida informações
- **Classificadora** — classifica sinais de acompanhamento
- **Recuperadora de contexto** — busca e ranqueia conhecimento relevante
- **Aceleradora de fluxo** — automatiza etapas operacionais
- **Geradora de apoio informacional** — produz relatórios de suporte

A IA **não** deve ser tratada como agente autônomo de decisão clínica.

---

## 4. Onde a IA atua na plataforma

### 4.1. Atendimento e acolhimento
- Acolher, explicar fluxo, responder perguntas frequentes
- Coletar informações iniciais e conduzir triagem básica

### 4.2. Anamnese assistida
- Estruturar perguntas e consolidar respostas
- Organizar dados em formato clínico legível
- Identificar lacunas de informação

### 4.3. Preparação pré-consulta
- Resumir histórico e organizar exames
- Gerar visão consolidada do caso
- Recuperar evidências científicas (RAG)
- Preparar relatório de apoio ao médico com doses, formulações e literatura correlata

### 4.4. Acompanhamento
- Classificar respostas de questionários
- Detectar sinais de atenção e sugerir prioridade
- Resumir evolução e preparar relatório para o médico

### 4.5. Operação interna
- Automatizar mensagens e organizar filas
- Categorizar atendimentos e consolidar indicadores

---

## 5. Limites obrigatórios da IA

A IA **não** pode:

- Prescrever autonomamente
- Validar diagnóstico final sem médico
- Tomar decisão clínica final
- Substituir assinatura médica
- Operar como fonte única de verdade científica sem governança

> Toda recomendação ou sugestão gerada pela IA deve ser tratada como **apoio**, nunca como ordem clínica.

---

## 6. Conceito de RAG na CannabIA

RAG (Retrieval-Augmented Generation) é o mecanismo pelo qual a plataforma **recupera conhecimento relevante de uma base estruturada** para enriquecer o contexto da geração.

**O RAG será usado para:**

- Apoio ao relatório científico pré-consulta
- Busca de evidências relacionadas ao diagnóstico e sintomas
- Apoio à base de conhecimento operacional
- Contextualização clínica por caso
- Futura expansão para suporte interno da equipe

---

## 7. Papel do banco vetorial

O banco vetorial é a **camada de memória semântica** da plataforma.

**Capacidades necessárias:**

- Indexação por embeddings
- Recuperação por similaridade semântica
- Filtro por tipo de fonte, tema e especialidade
- Filtro por tenant (quando aplicável)
- Versionamento lógico de documentos
- Desativação de conteúdos inválidos

---

## 8. Fontes de conhecimento previstas

### Fontes externas
- PubMed (estratégica)
- Literatura médica validada e indexada
- Diretrizes clínicas
- Bases regulatórias

### Fontes internas
- Protocolos próprios da operação
- Materiais curados pela organização-mãe
- Documentos das associações parceiras
- Conteúdo operacional e FAQs
- Histórico anonimizado (quando juridicamente permitido)

---

## 9. Tipos de conhecimento no sistema

| Tipo | Descrição |
|------|-----------|
| **Científico** | Artigos, publicações, revisões, estudos clínicos |
| **Clínico-operacional** | Protocolos, critérios de acompanhamento, orientações estruturadas |
| **Institucional** | Conteúdo do tenant, orientações próprias, materiais internos |
| **Conversacional/suporte** | FAQs, scripts de atendimento, explicações orientativas |

Essa separação ajuda a governança e evita mistura inadequada de fontes.

---

## 10. Fluxo conceitual RAG

```
Paciente fornece dados
    → Sistema estrutura anamnese
        → Caso resumido em representação consultável
            → Motor de recuperação busca conteúdos correlatos
                → Resultados filtrados, ranqueados e organizados
                    → IA usa esses conteúdos como contexto
                        → Relatório ou resposta é gerado
                            → Saída auditada e vinculada ao caso
```

---

## 11. Integração com PubMed

A integração com PubMed deverá permitir:

- Busca por termos clínicos, sintomas e condições
- Busca por canabinoides e composições terapêuticas
- Recuperação de títulos, abstracts e metadados

**Dois modos de operação:**

| Modo | Uso |
|------|-----|
| **Busca em tempo real** | Consultas pontuais ou enriquecimento dinâmico |
| **Ingestão periódica** | Formação do banco vetorial com curadoria governada |

> A ingestão periódica é preferível para produção: facilita governança, rastreabilidade e curadoria.

---

## 12. Governança do conhecimento

A CannabIA deve tratar o conhecimento como **ativo governado**.

**Atributos obrigatórios de cada item de conhecimento:**

```
origem, data_ingestao, versao, categoria,
status_validade, curadoria_responsavel,
motivo_ativacao_inativacao, rastreabilidade_de_uso
```

---

## 13. Status de curadoria de conteúdo

```
rascunho → ingerido → em_curadoria → aprovado
→ restrito | inativo | obsoleto
```

---

## 14. Níveis de confiança do conhecimento

| Nível | Exemplos |
|-------|---------|
| **Alto** | Diretriz, protocolo aprovado, artigo curado e validado |
| **Médio** | Artigo indexado com boa aderência, não aprovado especificamente |
| **Baixo** | Material não validado plenamente, conteúdo institucional exploratório |

A IA deve considerar o nível de confiança ao compor relatórios e respostas.

---

## 15. Uso clínico versus uso operacional

| Tipo | Exemplos | Governança |
|------|---------|------------|
| **Clínico-informacional** | Relatório pré-consulta, evidências científicas | Alta — validação humana necessária |
| **Operacional** | FAQ, scripts, explicações gerais | Média — conteúdo orientativo |

Um conteúdo que serve para suporte operacional **pode não servir** como apoio clínico.

---

## 16. Multi-tenancy do conhecimento

| Base | Responsável | Conteúdo |
|------|------------|---------|
| **Global** | Organização-mãe | Científico, regulatório, operacional global |
| **Por tenant** | Tenant contratante | Protocolos locais, FAQs próprios, materiais específicos |

---

## 17. Auditoria do uso de IA e RAG

Toda execução relevante de IA e recuperação contextual deve ser auditável:

```
entrada_usada, contexto_recuperado, fontes_consultadas,
trechos_usados, modelo_executado, resultado_final,
identificador_caso, tenant_id, medico_relacionado,
custo_estimado, timestamp
```

---

## 18. Saídas geradas pela IA

| Saída | Contexto |
|-------|---------|
| Resumo de anamnese | Pré-consulta |
| Relatório preparatório do caso | Pré-consulta |
| Síntese de exames | Pré-consulta |
| Relatório científico | Pré-consulta |
| Classificação de acompanhamento | Pós-consulta |
| Resumo da evolução | Acompanhamento |
| Apoio ao atendimento inicial | Acolhimento |

---

## 19. Política de segurança informacional da IA

- Validação de entrada e prevenção de prompt injection
- Limitação de escopo de contexto por tenant
- Proteção contra mistura indevida de dados entre tenants
- Filtragem de conteúdo sensível
- Trilha de auditoria completa de cada execução

---

## 20. Regras aprovadas neste documento

- A IA é camada de apoio — não de decisão clínica final
- O médico continua como responsável final
- O RAG é parte estrutural do produto
- O banco vetorial funciona como memória semântica
- PubMed é fonte estratégica de conhecimento
- Haverá distinção entre base global e base por tenant
- O conhecimento terá governança, status e rastreabilidade
- O uso de IA e RAG será auditável
- Conteúdos em contexto clínico exigem maior governança

---

## 21. Pontos para aprofundamento posterior

- Escolha final do banco vetorial (Chroma, Pinecone, pgvector etc.)
- Estratégia de embeddings
- Pipeline de ingestão do PubMed
- Esquema de metadados do conhecimento
- Ranking e re-ranking de recuperação
- Política de expiração de conteúdo
- Camada de segurança anti-injeção
- Arquitetura de prompts versionados

---

## 22. Conclusão

A arquitetura de IA da CannabIA deve ser construída como uma **infraestrutura de apoio confiável, auditável e governada**, capaz de transformar dados clínicos e conhecimento científico em suporte útil para médicos, agentes e operação.

O RAG e o banco vetorial são parte da espinha dorsal do diferencial da plataforma — especialmente na preparação de consulta, no apoio científico e na organização do conhecimento do ecossistema.
