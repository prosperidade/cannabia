# 27 — Biblioteca de Templates Regulatórios

## 1. Propósito do documento

Este documento especifica a **Biblioteca de Templates Regulatórios** da CannabIA: o conjunto de modelos parametrizáveis a partir dos quais o Sandbox Compliance Core (SCC) gera automaticamente os documentos exigidos pela RDC 1.014/2026 e pelo Edital de Chamamento da ANVISA.

A biblioteca cobre:

- Os cinco planos obrigatórios do Projeto Experimental.
- O Dossiê de Elegibilidade.
- O Parecer Final de Monitoramento do Experimento.
- Documentos complementares (consentimento, rotulagem, advertências).

Seu objetivo é transformar o Regulatory Reporting do SCC de "agregador de dados" em **gerador automático de documentos submissíveis**, reduzindo drasticamente o custo de candidatura e operação da associação.

---

## 2. Princípios da biblioteca

### 2.1. Separação entre dado, template e documento

- **Dado** — vive no banco, estruturado, versionado.
- **Template** — vive na biblioteca, é o molde com marcadores parametrizados e regras de preenchimento.
- **Documento** — é o resultado da fusão (`template + dados + configuração`) em um artefato final (PDF/A, DOCX ou Markdown).

Separar essas três camadas permite que o mesmo template gere documentos para qualquer associação sem duplicação, que templates sejam versionados independentemente dos dados, e que a evolução regulatória seja absorvida atualizando o template sem alterar os dados.

### 2.2. Edital-adaptável por design

A arquitetura é **edital-agnóstica na estrutura** e **edital-adaptável na parametrização**. Enquanto o Edital de Chamamento não é publicado, a biblioteca opera com parâmetros provisórios baseados no texto da RDC 1.014/2026. Quando o Edital for publicado, os parâmetros são ajustados sem necessidade de refatorar a arquitetura.

### 2.3. Versionamento formal

Cada template tem versão imutável. Documentos gerados carregam a versão do template usado. Uma nova versão do template não invalida documentos já gerados com versões anteriores — permite que a associação mantenha histórico coerente.

### 2.4. Aprovação bilateral

Documentos gerados passam por fluxo formal:

- Geração automática a partir dos dados atuais.
- Revisão pelo Responsável Técnico da associação.
- Revisão opcional pela consultoria jurídica parceira (quando contratada).
- Aprovação formal com assinatura eletrônica.
- Submissão à ANVISA via Regulatory Reporting.

### 2.5. Idioma e forma

Todos os templates são em **português do Brasil**, em registro técnico-formal, com terminologia aderente à da ANVISA. Formatação segue o padrão institucional da CannabIA com adaptação white-label por tenant (logotipo, identidade visual, dados da associação).

---

## 3. Arquitetura técnica da biblioteca

### 3.1. Estrutura de diretório

```
templates/
├── registry.yaml                    # Manifesto de todos os templates e versões
├── common/
│   ├── partials/                    # Componentes reutilizáveis (cabeçalho, rodapé, assinatura)
│   └── styles/                      # Estilos de formatação
├── eligibility/
│   ├── dossier_v1.md                # Template do Dossiê de Elegibilidade
│   └── schema_v1.yaml               # Schema de dados esperado
├── project_plans/
│   ├── work_plan_v1.md              # Plano de Trabalho Geral e Critérios Técnicos
│   ├── communication_plan_v1.md     # Plano de Comunicação, Transparência e Publicidade
│   ├── discontinuity_plan_v1.md     # Plano de Descontinuidade das Atividades
│   ├── monitoring_plan_v1.md        # Plano de Monitoramento
│   └── risk_management_plan_v1.md   # Plano de Gerenciamento e Mitigação de Riscos
├── operational/
│   ├── consent_form_v1.md
│   ├── label_warning_v1.md
│   └── sop_template_v1.md
└── final/
    ├── monitoring_opinion_v1.md     # Parecer Final de Monitoramento
    └── regulatory_report_v1.md      # Relatório Técnico-Regulatório Consolidado
```

### 3.2. Linguagem de template

Os templates usam uma linguagem declarativa simples, combinando:

- **Marcadores de substituição** — `{{ caminho.do.campo }}` para valores diretos.
- **Iteração** — `{% for item in colecao %} ... {% endfor %}` para listas.
- **Condicionais** — `{% if condicao %} ... {% endif %}` para seções opcionais.
- **Inclusão de partials** — `{% include "common/partials/signature" %}`.
- **Cálculos derivados** — `{{ calc("anos_operacao", data_inicio=...) }}`.

A engine escolhida pode ser **Jinja2** (Python, coerente com o stack Flask) ou **MDX** (quando a geração envolver componentes React). A recomendação padrão é Jinja2 pela aderência ao backend existente.

### 3.3. Schema de dados por template

Cada template carrega um `schema_vX.yaml` que declara:

- Campos obrigatórios.
- Campos opcionais.
- Validações (tipo, formato, vigência).
- Fontes de dados (qual entidade do banco preenche qual campo).
- Transformações (formatação de datas, agregações, cálculos).

O renderizador valida os dados contra o schema antes de gerar. Ausência de campo obrigatório interrompe a geração com erro explícito apontando onde preencher.

### 3.4. Registry central

`templates/registry.yaml` é o manifesto único da biblioteca, contendo:

- Lista de todos os templates ativos.
- Versão corrente de cada um.
- Vínculo com normas regulatórias de referência (RDC 1.014/2026, artigos específicos).
- Log de mudanças por versão.
- Status (`active`, `deprecated`, `under_review`).

---

## 4. Templates dos cinco planos obrigatórios

Esta seção descreve a estrutura lógica de cada um dos cinco planos exigidos pelo Art. 9º da RDC 1.014/2026. O texto final de cada template é produzido em arquivo próprio dentro da biblioteca, a partir desta especificação.

### 4.1. Plano de Trabalho Geral e Critérios Técnicos

**Objetivo:** descrever o escopo do Projeto Experimental, a metodologia, o cronograma e os critérios técnicos aplicados.

**Seções estruturais:**

1. Identificação da associação proponente.
2. Qualificação do Responsável Técnico.
3. Objetivo do Projeto Experimental.
4. Escopo das atividades propostas (cultivo, extração, preparação, dispensação).
5. Metodologia técnica por etapa.
6. Critérios técnicos de qualidade.
7. Infraestrutura disponível.
8. Recursos humanos e formação.
9. Escala proposta (volumes, número de associados beneficiados).
10. Cronograma por fase.
11. Interdependências com outros planos.
12. Assinaturas.

**Dados de origem:** `tenants`, `associations`, `technical_responsibles`, `technical_operational_capacity`, `sops` ativos, `sandbox_projects`.

**Cálculos derivados:** anos de operação da associação, capacidade instalada consolidada, cobertura de SOPs por área.

### 4.2. Plano de Comunicação, Transparência e Publicidade

**Objetivo:** estabelecer como a associação comunica-se com seus associados, com a ANVISA e com o público, respeitando as vedações de publicidade do Sandbox.

**Seções estruturais:**

1. Princípios de comunicação.
2. Reconhecimento das vedações (não é medicamento; não há comercialização; não há publicidade).
3. Canais oficiais da associação.
4. Processo de moderação regulatória de conteúdo.
5. Governança da comunicação com associados.
6. Governança da comunicação com a ANVISA e autoridades.
7. Governança da comunicação pública e institucional.
8. Resposta a demandas de imprensa.
9. Ciclo de revisão do plano.

**Dados de origem:** configuração de canais do tenant, política de moderação, histórico de submissões regulatórias.

**Regra invariante:** o sistema bloqueia, por design, conteúdo que caracterize publicidade. Essa regra é declarada explicitamente no plano e é validada pelo Communication Governance do SCC.

### 4.3. Plano de Descontinuidade das Atividades

**Objetivo:** descrever como a associação encerra as atividades do Projeto Experimental ao final do ciclo, em caso de suspensão pela ANVISA ou por decisão interna, preservando segurança sanitária e bem-estar dos associados.

**Seções estruturais:**

1. Cenários previstos de descontinuidade (natural, por suspensão, por decisão interna).
2. Critérios de ativação de cada cenário.
3. Procedimentos de encerramento do cultivo.
4. Procedimentos de destinação de insumos e preparados.
5. Procedimentos de transição para regime regulatório ordinário.
6. Comunicação aos associados.
7. Continuidade de cuidado para associados em tratamento.
8. Preservação de registros e evidências.
9. Responsabilidades de cada função.
10. Cronograma padrão de descontinuidade.

**Dados de origem:** `sandbox_projects`, `sandbox_protocols`, inventário atual de cultivo, preparados em estoque, associados em tratamento ativo.

### 4.4. Plano de Monitoramento

**Objetivo:** descrever os indicadores obrigatórios acompanhados pelo Grupo Técnico da ANVISA, a frequência de reporte e a metodologia de cálculo.

**Seções estruturais:**

1. Conjunto de indicadores obrigatórios.
2. Conjunto de indicadores complementares.
3. Metodologia de cálculo de cada indicador.
4. Frequência de reporte por indicador.
5. Infraestrutura de coleta de dados.
6. Processo de validação interna dos indicadores.
7. Formato de entrega à ANVISA.
8. Critérios de desvio e resposta.
9. Governança da revisão dos indicadores.

**Indicadores mínimos previstos (parametrizáveis pelo Edital):**

- Custo por paciente atendido.
- Custo por grama produzida.
- Taxa de conformidade laboratorial.
- Tempo médio de dispensação.
- Índice de rastreabilidade.
- Taxa de retenção de associados.
- Volume dispensado por período.
- Volume produzido por período.
- Número de eventos adversos por categoria.
- Taxa de adesão ao acompanhamento clínico.

**Dados de origem:** `sandbox_indicators`, `sandbox_indicator_values`, agregações do Evidence Engine.

### 4.5. Plano de Gerenciamento e Mitigação de Riscos Sanitários

**Objetivo:** descrever a matriz de riscos sanitários identificados, os controles aplicados e o processo contínuo de gestão.

**Seções estruturais:**

1. Metodologia de identificação e classificação de riscos.
2. Matriz de riscos ativa.
3. Controles por risco.
4. Responsáveis por risco.
5. Verificação de eficácia de controles.
6. Processo de revisão periódica.
7. Integração com farmacovigilância.
8. Integração com CAPAs.
9. Governança da matriz de riscos.

**Dados de origem:** `sanitary_risks`, `risk_controls`, `sop_deviations`, `capa_actions`, `adverse_events`.

---

## 5. Dossiê de Elegibilidade

### 5.1. Propósito

Documento apresentado à ANVISA no momento da submissão ao Edital, atestando que a associação cumpre os requisitos de elegibilidade do Sandbox Regulatório.

### 5.2. Estrutura

1. Identificação institucional completa.
2. Comprovação de natureza jurídica sem fins lucrativos.
3. Comprovação de tempo mínimo de constituição.
4. Qualificação do Responsável Técnico.
5. Matriz de Capacidade Técnico-Operacional.
6. Inventário de documentos institucionais vigentes.
7. Inventário de POPs e cobertura por área.
8. Histórico de farmacovigilância quando aplicável.
9. Declaração de conformidade com vedações do Sandbox.
10. Declarações e assinaturas.

### 5.3. Dados de origem

`tenants`, `associations`, `institutional_documents`, `technical_responsibles`, `technical_operational_capacity`, `sops`, métricas de histórico operacional.

### 5.4. Auto-preenchimento

A meta operacional é que 90% ou mais dos campos do Dossiê sejam **preenchidos automaticamente** a partir do que a associação já mantém no sistema. Campos restantes recebem avisos explícitos sobre o que falta e como preencher.

---

## 6. Parecer Final de Monitoramento do Experimento

### 6.1. Propósito

Documento produzido ao final do Projeto Experimental, consolidando os resultados, dados e aprendizados do ciclo, nos termos do Art. 20 da RDC 1.014/2026.

### 6.2. Estrutura

1. Resumo executivo.
2. Escopo e objetivos originais do Projeto.
3. Cumprimento do cronograma.
4. Desempenho dos indicadores obrigatórios por período.
5. Desempenho dos indicadores complementares.
6. Evidências operacionais (SOPs, desvios, CAPAs).
7. Evidências clínicas e de desfecho.
8. Histórico de farmacovigilância.
9. Ancoragens em blockchain pública e integridade da rastreabilidade.
10. Achados relevantes e aprendizados.
11. Recomendações para futura regulação.
12. Limitações do experimento.
13. Prestação de contas financeira quando aplicável.
14. Anexos.

### 6.3. Dados de origem

Praticamente todas as entidades do SCC, agregadas por período do Projeto Experimental: `sandbox_indicator_values`, `traceability_events` agregados, `adverse_events`, `sop_evidences` agregados, `dispensations`, `lab_analyses`, `blockchain_anchors`, estudos observacionais do Evidence Engine.

### 6.4. Ciclo de geração

O Parecer Final não é gerado em um único momento — ele acumula ao longo do ciclo:

- Trimestralmente, versão parcial é gerada e arquivada.
- Ao final do Projeto, versão final consolida o acumulado e adiciona seções de recomendações e limitações.
- Revisão pelo Responsável Técnico e pela consultoria jurídica parceira quando contratada.
- Aprovação formal e submissão à ANVISA via Regulatory Reporting.

---

## 7. Documentos operacionais complementares

### 7.1. Termo de Consentimento Informado do Associado

Template parametrizável cobrindo:

- Identificação da associação.
- Natureza experimental do Sandbox.
- Advertência de que o produto não é medicamento.
- Uso de dados pessoais (LGPD).
- Compartilhamento anonimizado com a ANVISA.
- Direitos do associado (retirada de consentimento, apagamento de dados).
- Riscos e benefícios conhecidos.
- Assinatura eletrônica ou física com evidência registrada.

### 7.2. Rótulo e Advertência de Preparados

Template que gera rótulo em conformidade com:

- Identificação do preparado.
- Perfil de canabinoides.
- Lote e data de preparação.
- Advertência expressa de que não é medicamento e não foi aprovado pela ANVISA.
- QR Code de verificação pública.
- Identificação do Responsável Técnico.
- Identificação da associação.

### 7.3. Template de POP

Template-base para criação de novos POPs, garantindo estrutura mínima:

- Identificação e código do POP.
- Objetivo.
- Escopo e aplicabilidade.
- Definições.
- Responsabilidades.
- Procedimento detalhado.
- Registros gerados.
- Referências normativas.
- Histórico de revisões.
- Aprovação.

---

## 8. Fluxo de geração de documento

### 8.1. Passo a passo

1. **Solicitação.** Usuário autorizado solicita geração de um documento específico via Regulatory Reporting.
2. **Seleção de template e versão.** Sistema identifica o template apropriado na versão corrente do registry.
3. **Carga de dados.** Sistema executa queries estruturadas no banco para popular os campos do schema do template.
4. **Validação.** Schema é validado. Se houver campo obrigatório faltando, o sistema retorna lista de pendências antes de gerar.
5. **Renderização.** Engine de template produz o documento intermediário em Markdown.
6. **Conversão.** Documento é convertido para formato final (PDF/A para submissão oficial, DOCX para edição, MD para uso interno).
7. **Hash e persistência.** Documento é hasheado e armazenado em `regulatory_reports`.
8. **Revisão.** Responsável Técnico revisa e aprova ou solicita ajustes.
9. **Aprovação formal.** Assinatura eletrônica é aplicada. Documento torna-se versão oficial.
10. **Submissão.** Documento oficial é submetido à ANVISA via canal apropriado e registrado em `regulatory_submissions`.

### 8.2. Ciclo de revisão

A associação pode editar manualmente seções específicas do documento gerado antes da aprovação formal. O sistema mantém:

- Versão original gerada pelo template.
- Versão editada pelo Responsável Técnico.
- Diff entre as versões.
- Justificativa da edição.

Tudo isso fica auditável.

### 8.3. Geração em lote

Ao final do ciclo, o sistema pode gerar em lote os cinco planos obrigatórios, o Parecer Final, o Relatório Técnico-Regulatório Consolidado e o Dossiê atualizado, produzindo o pacote completo de submissão em uma única operação.

---

## 9. Versionamento e evolução dos templates

### 9.1. Política de versão

- **Major** — mudança estrutural no template (novas seções, remoção de campos) ou mudança de norma de referência. Exemplo: atualização do template após publicação do Edital.
- **Minor** — ajustes estruturais sem quebra de dados (renomeação de seções, adição de campos opcionais).
- **Patch** — correções textuais, formatação, clareza.

### 9.2. Migração de documentos

Documentos já gerados com versão anterior **não são automaticamente regerados**. Eles permanecem como registros históricos válidos.

Quando um documento precisa ser refeito (ex.: submissão atualizada à ANVISA), o usuário explicitamente solicita regeração com a versão atual do template.

### 9.3. Depreciação

Templates depreciados permanecem no registry com status `deprecated` e não podem ser usados para novas gerações. Documentos gerados com eles continuam válidos.

### 9.4. Mudança de norma regulatória

Quando uma norma de referência é alterada (ex.: atualização da RDC 1.014/2026 ou publicação do Edital de Chamamento), o processo é:

1. Análise de impacto sobre os templates afetados.
2. Criação de nova major version dos templates impactados.
3. Comunicação formal aos tenants.
4. Período de transição durante o qual ambas as versões coexistem.
5. Depreciação da versão antiga após conclusão da transição.

---

## 10. Integração com o Regulatory Reporting

A Biblioteca de Templates Regulatórios é o **backend de conteúdo** do Regulatory Reporting do SCC.

### 10.1. Responsabilidades divididas

| Regulatory Reporting | Biblioteca de Templates |
|---|---|
| Interface do usuário | Templates e schemas |
| Orquestração do fluxo | Engine de renderização |
| Controle de aprovações | Registry e versionamento |
| Submissão à ANVISA | Partials e estilos |
| Auditoria de submissões | Validação de dados |

### 10.2. API interna

O Regulatory Reporting consome a biblioteca por API interna:

```
POST /internal/templates/render
{
    "template_id": "project_plans/work_plan",
    "version": "v1",
    "tenant_id": 42,
    "project_id": 7,
    "output_format": "pdf"
}
```

Retorna o documento gerado, seu hash e a lista de pendências caso existam.

### 10.3. Cache

Documentos gerados são cacheados por (template_version, dados_hash). Uma nova geração só ocorre se os dados de origem mudaram ou se o template foi atualizado.

---

## 11. Riscos e mitigações

### 11.1. Risco de descolamento entre template e norma

Um template desatualizado pode gerar documento que não atende mais à norma vigente. **Mitigação:** revisão trimestral da biblioteca contra monitor regulatório (ANVISA e DOU) que já existe na plataforma.

### 11.2. Risco de dado incompleto mascarado

Templates podem esconder ausência de dados com valores padrão genéricos, produzindo documento superficialmente correto mas inadequado. **Mitigação:** schema obrigatório + validação rigorosa + lista explícita de pendências antes da geração.

### 11.3. Risco de personalização excessiva

Edições manuais podem descaracterizar o documento e introduzir inconformidades. **Mitigação:** diff auditável entre versão original e editada, e obrigação de justificativa textual para cada edição.

### 11.4. Risco de lock-in

Engine proprietária de template pode dificultar portabilidade. **Mitigação:** uso de Jinja2 como engine padrão (tecnologia aberta), schemas em YAML, output em formatos padronizados.

### 11.5. Risco de interpretação jurídica incorreta

Templates incorporam interpretação da RDC. Se a interpretação estiver errada, o erro se propaga em todos os documentos gerados. **Mitigação:** revisão jurídica da biblioteca por consultoria parceira antes da entrada em produção e a cada major version.

---

## 12. Papéis e responsabilidades

| Papel | Responsabilidades |
|---|---|
| **Time de Produto / Compliance CannabIA** | Manter a biblioteca, criar novas versões, responder a mudanças regulatórias |
| **Consultoria jurídica parceira** | Revisar templates antes de major versions, validar interpretações normativas |
| **Responsável Técnico da associação** | Revisar documentos gerados, aprovar, assinar |
| **Regulatory Reporting do SCC** | Orquestrar o fluxo de geração, aprovação e submissão |
| **Associação** | Fornecer dados operacionais que alimentam os templates via uso normal da plataforma |

---

## 13. Pontos para aprofundamento posterior

- Texto integral de cada template em sua versão v1.
- Schemas YAML completos de cada template.
- Mapeamento campo a campo entre schema e queries SQL.
- Biblioteca de partials reutilizáveis.
- Estilos de formatação institucional.
- Fluxo detalhado de assinatura eletrônica.
- Modelo de revisão jurídica com tempos de resposta esperados.
- Processo de feedback das associações para evolução dos templates.
- Possibilidade de oferecer editor visual de template para tenants Enterprise customizarem partes não-normativas.

---

## 14. Regras aprovadas neste documento

Ficam aprovadas como base oficial:

- Dado, template e documento são camadas separadas e versionadas.
- Todos os templates obrigatórios do Sandbox são mantidos na biblioteca.
- Geração automática a partir de dados operacionais é o modo padrão.
- Validação contra schema é obrigatória antes da renderização.
- Edição manual é permitida mas auditável, com justificativa e diff.
- Versionamento segue major/minor/patch, com coexistência de versões durante transições.
- Mudanças regulatórias disparam análise de impacto formal.
- A engine padrão é Jinja2, com schemas em YAML e output em PDF/A, DOCX e Markdown.
- Revisão jurídica é obrigatória antes de entrada em produção e a cada major version.
- Documentos gerados são hasheados, persistidos em `regulatory_reports` e cobertos por ancoragem em blockchain quando aplicável.
- O Parecer Final é construído incrementalmente ao longo do ciclo do Projeto.
- 90% ou mais dos campos devem ser preenchidos automaticamente no Dossiê de Elegibilidade.

---

## 15. Conclusão

A Biblioteca de Templates Regulatórios é o último componente fundamental do Sandbox Compliance Core. Com ela, o SCC completa a promessa do plano Sandbox Ready: transformar dados operacionais corretos em **documentos submissíveis à ANVISA com intervenção humana mínima e qualidade regulatória auditável**.

A combinação entre:

- Modelagem de dados rigorosa (doc 24)
- Rastreabilidade imutável ancorada publicamente (doc 25)
- Geração automática de documentos normativos (este documento)
- Programa piloto com caso-referência real (doc 23)
- Arquitetura transversal governada (doc 22)

fecha o quinteto que materializa a CannabIA como infraestrutura operacional, clínica, científica e regulatória de referência para o ecossistema associativo brasileiro diante do Sandbox Regulatório da ANVISA.

Os documentos subsequentes da série podem agora avançar para aspectos específicos — contratos comerciais, integrações externas detalhadas, guias operacionais — sabendo que a fundação conceitual, técnica e regulatória está consolidada nos documentos 22 a 26.
