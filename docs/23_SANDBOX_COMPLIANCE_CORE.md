# 23 — Sandbox Compliance Core

## 1. Propósito do documento

Este documento define o **Sandbox Compliance Core (SCC)**, o módulo transversal da plataforma CannabIA destinado a tornar associações de pacientes operacionalmente, clinicamente e documentalmente aderentes às exigências do **Sandbox Regulatório da ANVISA**, instituído pela RDC nº 1.014/2026.

O SCC é ao mesmo tempo:

- A camada de **preparação pré-edital**, que leva a associação de "operando em zona cinzenta" a "elegível e competitiva" no Chamamento Público.
- A camada de **operação durante o sandbox**, que sustenta a rotina técnica, clínica e de rastreabilidade da associação sob supervisão da ANVISA.
- A camada de **encerramento e prestação de contas**, que materializa o Parecer Final de Monitoramento e subsidia o Relatório Técnico-Regulatório Consolidado e a Análise de Resultado Regulatório (ARR).

Seu objetivo é consolidar, em um único módulo integrado, todas as funcionalidades, entidades, trilhas de auditoria, fluxos operacionais e artefatos documentais que uma associação precisa para ingressar, operar e encerrar um Projeto Experimental no ambiente regulatório experimental da ANVISA.

---

## 2. Contexto regulatório

### 2.1. Base legal

O SCC se apoia em três camadas normativas hierárquicas:

| Norma | Função |
|---|---|
| **Lei Complementar nº 182/2021 (Marco Legal das Startups), Art. 11** | Autoriza órgãos reguladores a instituírem sandboxes regulatórios no Brasil |
| **RDC ANVISA nº 1.014/2026** | Institui o Sandbox Regulatório específico para cannabis medicinal e associações de pacientes |
| **Edital de Chamamento Público (a ser publicado)** | Detalhamento operacional, critérios de elegibilidade, indicadores obrigatórios e requisitos técnicos específicos |

O SCC é projetado para ser **edital-agnóstico na estrutura** e **edital-adaptável na parametrização**: a arquitetura é estável; os campos, limites e checklists são configuráveis por meio de parâmetros governados pela organização-mãe quando o edital for publicado.

### 2.2. Natureza do Sandbox Regulatório

O Sandbox da ANVISA é um ambiente regulatório:

- **Experimental** — destinado a testagem controlada.
- **Excepcional e transitório** — não estabelece regime permanente.
- **Supervisionado** — por Grupo Técnico Específico da ANVISA.
- **Temporário** — duração máxima de 5 anos, contados do início do Protocolo de Adequação Regulatória Experimental.
- **Orientado à geração de evidências** — dados e achados regulatórios são o produto final.
- **Não comercial** — a comercialização é absolutamente vedada.
- **Sem direito adquirido** — não equivale a registro de produto nem autoriza atividade permanente.

### 2.3. Perfil dos participantes

Apenas pessoas jurídicas sem fins lucrativos (associações de pacientes) com pelo menos 2 anos de constituição podem participar. O fornecimento de preparados é restrito ao uso medicinal pessoal de associados regularmente cadastrados, sem atividade comercial e sem publicidade.

### 2.4. Ciclo de vida do Projeto Experimental

1. Publicação do Edital de Chamamento pela Dicol/ANVISA.
2. Submissão de projeto pela associação interessada.
3. Seleção mediante critérios técnicos, sanitários e de elegibilidade.
4. Pactuação do Protocolo de Adequação Regulatória Experimental entre ANVISA e participante.
5. Emissão de Autorização Temporária (AT).
6. Execução do Projeto Experimental sob supervisão.
7. Monitoramento contínuo por indicadores obrigatórios.
8. Parecer Final de Monitoramento do Experimento.
9. Consolidação em Relatório Técnico-Regulatório.
10. Análise de Resultado Regulatório (ARR) pela ANVISA.

O SCC cobre **do passo 2 ao passo 9**, gerando artefatos estruturados que subsidiam o passo 10.

---

## 3. Tese do módulo

O SCC operacionaliza a seguinte tese:

> **A CannabIA é a infraestrutura operacional, clínica e documental que torna a associação auditável, rastreável e elegível para o Sandbox Regulatório da ANVISA desde o primeiro paciente atendido.**

O módulo é projetado para que uma associação que opere 100% dentro da CannabIA, no plano Sandbox Ready, chegue ao Edital de Chamamento com:

- Dossiê de elegibilidade pré-montado.
- Biblioteca viva de POPs com evidências de aplicação.
- Rastreabilidade seed-to-patient auditável com ancoragem criptográfica.
- Registro estruturado de associados regularmente cadastrados.
- Histórico de farmacovigilância estruturado.
- Trilha de auditoria completa por evento.
- Dados clínicos longitudinais e desfechos terapêuticos.
- Os cinco planos obrigatórios gerados automaticamente.
- Indicadores de monitoramento calculados em tempo real.

A proposta não garante aprovação — a aprovação é prerrogativa da ANVISA. A proposta **maximiza prontidão e minimiza custo de candidatura**.

---

## 4. Alinhamento com o marco regulatório

Esta seção mapeia cada exigência da RDC 1.014/2026 ao submódulo do SCC que a atende.

### 4.1. Elegibilidade e formalização

| Exigência | Atendimento pelo SCC |
|---|---|
| Pessoa jurídica sem fins lucrativos | Governance Hub valida natureza jurídica no cadastro |
| Mínimo de 2 anos de constituição | Governance Hub valida data de constituição automaticamente |
| Responsável Técnico legalmente habilitado | Governance Hub mantém cadastro, credenciais e vigência |
| Capacidade Técnico-Operacional | Governance Hub cruza infraestrutura × equipe × escala × processos |

### 4.2. Planos obrigatórios do Projeto Experimental

| Plano exigido pela RDC | Gerado/suportado por |
|---|---|
| Plano de Trabalho Geral e Critérios Técnicos | Governance Hub + Regulatory Reporting |
| Plano de Comunicação, Transparência e Publicidade | Communication Governance (subcomponente do Regulatory Reporting) |
| Plano de Descontinuidade das Atividades | Regulatory Reporting com templates e runbooks |
| Plano de Monitoramento | Indicators Engine (subcomponente do Evidence Engine) |
| Plano de Gerenciamento e Mitigação de Riscos Sanitários | Risk & Pharmacovigilance |

### 4.3. Requisitos técnico-sanitários mínimos

| Requisito | Atendimento |
|---|---|
| Procedimentos operacionais padrão de qualidade | SOPs & Quality Management com versionamento e evidência de uso |
| Perfil de canabinoides (CBD, THC e outros) | Seed-to-Patient Traceability com vínculo obrigatório a laudo analítico |
| Advertência expressa de não-medicamento | Dispensation Flow bloqueia dispensação sem advertência no rótulo |
| Evidência de uso de POPs | Sistema registra automaticamente adesão/desvio a cada execução |

### 4.4. Salvaguardas não flexibilizáveis (Art. 17)

A RDC estabelece três áreas que **não podem** ser moduladas nem flexibilizadas sob nenhuma hipótese. O SCC trata cada uma como **invariante arquitetural**, ou seja, não configurável por tenant:

| Salvaguarda | Tratamento arquitetural |
|---|---|
| Rastreabilidade e controle da planta e derivados | Hardcoded no Seed-to-Patient Traceability; sem flag de desativação |
| Notificação de eventos adversos | Hardcoded no módulo de Farmacovigilância; sem flag de desativação |
| Proteção de dados pessoais dos pacientes (LGPD) | Hardcoded no modelo de dados e políticas de acesso; sem flag de desativação |

Essa decisão arquitetural é registrada como **regra invariante** na governança da plataforma. Nenhum parâmetro de tenant, nenhuma customização white-label e nenhuma configuração comercial pode desligar essas três camadas.

### 4.5. Limites operacionais

| Limite | Enforcement pelo SCC |
|---|---|
| Vedação a comercialização | Dispensation Flow bloqueia qualquer operação com contrapartida financeira direta |
| Vedação a publicidade | Communication Governance submete conteúdo a moderação regulatória |
| Fornecimento exclusivo a associado cadastrado | Member Registry valida vínculo ativo antes de qualquer dispensação |
| Pequena escala, não industrial | Indicators Engine monitora volumes e emite alerta se limites previstos no Protocolo forem ultrapassados |
| Advertência de não-medicamento | Campo obrigatório em todo rótulo e toda comunicação com associado |

---

## 5. Arquitetura do Sandbox Compliance Core

O SCC é composto por sete submódulos integrados. Cada um é um domínio próprio, com entidades, fluxos e APIs específicas, que se conectam aos módulos já existentes da CannabIA.

### 5.1. Governance Hub

Responsável pelo **dossiê institucional e regulatório** da associação.

**Entidades principais:** associação (evolução de clinic com campos estatutários), responsável técnico, corpo diretivo, estatuto, atas, certidões, licenças sanitárias.

**Funcionalidades:**

- Cadastro estruturado com validação automática de elegibilidade (natureza jurídica, tempo de constituição).
- Gestão de documentos institucionais com controle de vigência e alerta de renovação.
- Registro e validação de habilitação do Responsável Técnico.
- Matriz de Capacidade Técnico-Operacional que cruza infraestrutura declarada, recursos humanos, processos ativos e escala proposta.
- Exportação do Dossiê de Elegibilidade em formato submissível ao Edital.

### 5.2. SOPs & Quality Management

Responsável pela **biblioteca viva de Procedimentos Operacionais Padrão** e pela evidência de aplicação.

**Entidades principais:** SOP, versão de SOP, treinamento, evidência de execução, desvio, CAPA (Corrective and Preventive Action).

**Funcionalidades:**

- Biblioteca de SOPs com versionamento, assinatura eletrônica e controle de vigência.
- Registro de treinamento por colaborador com comprovação de leitura e compreensão.
- Registro automático de execução: quando um fluxo operacional é executado, o sistema anota qual SOP foi aplicado e registra evidência.
- Registro de desvios com fluxo de CAPA.
- Disponibilidade em plano Premium com escopo reduzido; escopo completo no Sandbox Ready.

### 5.3. Seed-to-Patient Traceability

Responsável pela **rastreabilidade end-to-end** da planta ao paciente. É o submódulo mais sensível arquiteturalmente — detalhado em profundidade na Seção 6.

**Entidades principais:** lote de sementes ou matriz genética, planta individual, lote de cultivo, colheita, extração, insumo farmacêutico vegetal, preparado, unidade dispensada, evento de rastreabilidade.

**Funcionalidades:**

- Identificação única por QR Code em cada nível da cadeia.
- Registro de cada movimentação com timestamp, ator, georreferenciamento quando aplicável.
- Vínculo obrigatório a laudos analíticos de perfil de canabinoides em pontos-chave.
- Cadeia criptográfica append-only (detalhada na Seção 6).
- Ancoragem periódica em blockchain pública para prova de integridade (detalhada na Seção 6).
- Integração com SNGPC quando e se aplicável.
- Trilha pública consultável por fiscal via leitura de QR Code.

### 5.4. Member-Patient Registry

Responsável pelo **registro do associado regularmente cadastrado** — distinto do paciente genérico da plataforma atual.

**Entidades principais:** associado, vínculo associativo, prescrição médica vinculada ao uso pessoal, consentimento informado, prontuário longitudinal, histórico de dispensação.

**Funcionalidades:**

- Cadastro de associado com validação de vínculo associativo ativo, consentimento e prescrição válida.
- Validação obrigatória antes de qualquer dispensação.
- Evolução do módulo de prontuário existente para incorporar campos estatutários.
- Integração com o pipeline clínico e de IA já existente.
- Exportação estatística anonimizada para Evidence Engine.

### 5.5. Risk & Pharmacovigilance

Responsável pelo **Plano de Gerenciamento e Mitigação de Riscos Sanitários** e pela **notificação de eventos adversos**.

**Entidades principais:** matriz de riscos sanitários, controle, evento adverso, notificação, reação adversa, desdobramento clínico.

**Funcionalidades:**

- Matriz de riscos configurável com probabilidade, impacto, controle e responsável.
- Captura estruturada de eventos adversos pelo associado via WhatsApp, web ou durante consulta.
- Triagem clínica assistida por IA com classificação de severidade.
- Notificação automatizada à ANVISA via VigiMed/Notivisa quando aplicável, respeitando prazos regulatórios.
- Dashboard epidemiológico por período, condição, perfil de canabinoide e desfecho.
- Trilha de auditoria completa de cada notificação.
- Disponibilidade em plano Premium com escopo reduzido; escopo completo no Sandbox Ready.

### 5.6. Evidence & Real-World Data Engine

Responsável pela **coleta, estruturação e exportação de evidências regulatórias**. Este é o submódulo em que a CannabIA se diferencia decisivamente — pois é onde a IA, o RAG, o PubMed e a telemetria pós-consulta já existentes se convertem em valor regulatório concreto.

**Entidades principais:** desfecho clínico, patient-reported outcome, correlação dose-efeito, evento telemétrico, métrica agregada, estudo observacional.

**Funcionalidades:**

- Captura longitudinal de desfechos por condição clínica (dor, epilepsia, ansiedade, sono, espasticidade etc.).
- Integração com a telemetria pós-consulta existente (D+3, D+7, D+15).
- Correlação entre perfil de canabinoides do preparado, dose, via de administração e resposta terapêutica.
- Geração de estudos observacionais internos com metodologia reprodutível.
- Exportação estruturada para o Relatório Final de Monitoramento do Experimento.
- Potencial publicação científica em parceria com a associação.

### 5.7. Regulatory Reporting & Audit Trail

Responsável pela **interface de prestação de contas** com a ANVISA e pela **trilha de auditoria consolidada**.

**Entidades principais:** relatório regulatório, indicador obrigatório, evento de auditoria, submissão regulatória, consulta de fiscalização.

**Funcionalidades:**

- Dashboard "ANVISA-ready" com indicadores obrigatórios calculados em tempo real.
- Geração automática dos cinco planos obrigatórios exigidos pelo Projeto Experimental.
- Geração do Parecer Final de Monitoramento em formato submissível.
- Trilha de auditoria consolidada cobrindo: auditoria clínica, operacional, financeira, de qualidade, de segurança e de IA.
- Interface de resposta a consultas de fiscalização com rastreabilidade de quem consultou o quê e quando.
- Suporte à ancoragem criptográfica (ver Seção 6).

---

## 6. Imutabilidade e ancoragem em blockchain pública

Esta seção define a estratégia técnica da CannabIA para garantir integridade, auditabilidade e prova independente de rastreabilidade.

### 6.1. Decisão arquitetural

A plataforma **não usa blockchain como banco operacional**. Usa uma **arquitetura híbrida em três camadas** que entrega os benefícios reais de imutabilidade e auditabilidade independente sem herdar os custos, a complexidade e os conflitos com a LGPD inerentes ao uso amplo de blockchain.

### 6.2. Motivação da escolha

A rejeição da abordagem "blockchain para tudo" se apoia em três razões:

**Conflito com a LGPD.** Blockchain é imutável por design; a LGPD garante ao titular o direito de apagamento. Armazenar dados pessoais em blockchain cria conflito legal que a própria RDC 1.014/2026 reforça ao marcar a proteção de dados pessoais como invariante no Art. 17.

**Custo e complexidade operacional.** A escala de eventos em uma associação (cultivo, extração, produção, dispensação, SOPs, eventos adversos) gera volume incompatível com o custo de escrita em blockchain pública e com a complexidade de operar blockchain privada.

**Não-exigência regulatória.** A ANVISA exige rastreabilidade auditável e imutável. Ela não exige blockchain. Entregar blockchain onde a exigência é integridade verificável é marketing, não engenharia.

### 6.3. Camada 1 — Banco transacional append-only

Todas as operações de rastreabilidade, farmacovigilância, SOPs e auditoria são gravadas em PostgreSQL com:

- Tabelas append-only com triggers que impedem UPDATE e DELETE a nível de banco.
- Revogação de permissões de UPDATE e DELETE para todas as roles exceto a role de backup/compliance.
- Separação estrutural entre tabelas de evento (imutáveis, sem PII) e tabelas de contexto (com PII, apagáveis sob LGPD).
- Cada evento imutável referencia o contexto por ID, não por conteúdo — permitindo apagamento de PII sem quebrar a cadeia de eventos.

### 6.4. Camada 2 — Cadeia de hashes interna

Cada evento armazenado carrega um campo de hash criptográfico (SHA-256) calculado sobre:

- O conteúdo canônico do próprio evento.
- O hash do evento imediatamente anterior na mesma cadeia lógica (ex: cadeia por lote, cadeia por associação).

Isso forma uma **Merkle chain interna** dentro do banco de dados. Qualquer alteração retroativa, mesmo que conseguisse escapar das restrições da camada 1, quebra a cadeia de hashes e é imediatamente detectável.

### 6.5. Camada 3 — Ancoragem em blockchain pública

Periodicamente — diariamente, semanalmente ou em intervalos definidos por política — o sistema:

- Calcula a **raiz Merkle** de todos os eventos novos desde a última ancoragem.
- Submete essa raiz a uma blockchain pública via **OpenTimestamps (Bitcoin)** ou **Polygon**.
- Armazena a prova de ancoragem (transaction ID, bloco, timestamp) junto aos eventos cobertos.

O custo é de centavos a poucos reais por ancoragem. O resultado:

- Qualquer pessoa, incluindo a própria ANVISA, pode verificar independentemente que os registros da associação não foram adulterados após a data da ancoragem.
- Nenhum dado pessoal, clínico ou operacional é exposto publicamente — apenas a prova criptográfica.
- A LGPD permanece respeitada integralmente, pois PII nunca toca a chain.

### 6.6. Uso adicional opcional — NFT de identidade genética

Registros fundacionais imutáveis e sem PII podem ser inscritos diretamente em blockchain pública como tokens de identidade:

- Lote de sementes ou matriz genética.
- Identidade de strain.
- Certificados de origem.

Esses ativos não mudam, não contêm PII e beneficiam-se de serem publicamente verificáveis como um certificado. Para eventos operacionais (dispensações, consultas, SOPs), a arquitetura de três camadas continua sendo o caminho correto.

### 6.7. Consequências de posicionamento

A combinação das três camadas permite que a associação declare honestamente que sua rastreabilidade é **verificável em blockchain pública e independente de terceiros** — diferencial competitivo concreto diante de outros sistemas de gestão para associações.

---

## 7. Modelagem de dados proposta

O SCC introduz e estende entidades do modelo de dados da CannabIA. Esta seção lista as novas entidades e as extensões necessárias, em nível lógico. A modelagem física (DDL, migrations, índices) fica para o documento técnico subsequente.

### 7.1. Entidades novas

- `associations` — evolução tipada de `clinics` para tenants do tipo associação, com campos estatutários.
- `association_members` — vínculo formal entre pessoa e associação, com status e vigência.
- `technical_responsibles` — Responsáveis Técnicos com habilitação validada.
- `sops`, `sop_versions`, `sop_trainings`, `sop_evidences`, `sop_deviations`, `capa_actions` — biblioteca de SOPs e ciclo de qualidade.
- `seed_lots`, `genetic_matrices`, `plants`, `cultivation_batches`, `harvests`, `extractions`, `api_vegetables`, `preparations`, `dispensations` — cadeia de rastreabilidade.
- `traceability_events` — log append-only de todos os eventos de rastreabilidade, com hash encadeado.
- `lab_analyses` — laudos analíticos com perfil de canabinoides, vinculados a eventos de rastreabilidade.
- `adverse_events`, `pharmacovigilance_notifications` — farmacovigilância estruturada.
- `sanitary_risks`, `risk_controls` — matriz de riscos.
- `sandbox_projects`, `sandbox_protocols`, `sandbox_indicators`, `sandbox_submissions` — gestão do Projeto Experimental.
- `blockchain_anchors` — registros de ancoragem em blockchain pública com prova associada.
- `regulatory_reports` — relatórios gerados e submetidos.

### 7.2. Extensões a entidades existentes

- `clinics` → evolui para `tenants` com discriminador de tipo (clínica, associação, médico autônomo).
- `patients` → ganha vínculo opcional com `association_members` quando o tenant é associação.
- `prescriptions` → ganha campos de conformidade regulatória específicos do sandbox.
- `audit_log` → consolida eventos clínicos, operacionais, financeiros, de qualidade e de segurança, com hash encadeado.
- `ai_audits` → estendido para incluir decisões de IA em triagem de farmacovigilância.

---

## 8. Integrações

### 8.1. Reaproveitamento de capacidades existentes

| Capacidade existente | Uso no SCC |
|---|---|
| Multi-tenancy por `clinic_id`/`tenant_id` | Associação como tenant do tipo sandbox-ready |
| Pipeline de IA com auditoria | Base do Evidence Engine e da triagem de farmacovigilância |
| Prontuário longitudinal | Core do Member-Patient Registry |
| Telemetria pós-consulta D+3/D+7/D+15 | Captura de desfechos clínicos longitudinais |
| RAG + banco de conhecimento + PubMed | Atualização regulatória contínua e suporte à evidência |
| Prescrição determinística com Rules Engine e Safety Clamp | Trilha de prescrição zero-alucinação exigível em auditoria |
| WhatsApp Business | Canal primário de captura de eventos adversos e PRO |
| Auditoria de IA | Fundação da auditoria sanitária consolidada |

### 8.2. Integrações novas

- **SNGPC** — integração com o Sistema Nacional de Gerenciamento de Produtos Controlados quando aplicável.
- **VigiMed / Notivisa** — notificação de eventos adversos.
- **OpenTimestamps / Polygon** — ancoragem de raízes Merkle.
- **Laboratórios de análise de canabinoides** — ingestão estruturada de laudos analíticos.
- **Base de dados da Receita Federal / portal de transparência** — validação de natureza jurídica e tempo de constituição.

---

## 9. Distribuição entre planos comerciais

Esta seção atualiza o modelo de planos definido em `05_WHITE_LABEL_AND_MONETIZATION_MODEL.md`, incorporando o SCC.

### 9.1. Princípio de distribuição

Os componentes do SCC **descem parcialmente para Pro e Premium** como diferencial de qualidade, e a **camada completa Sandbox-Ready** fica reservada ao novo plano dedicado.

### 9.2. Distribuição por plano

| Componente | Basic | Pro | Premium | Sandbox Ready |
|---|---|---|---|---|
| Governance Hub | — | Parcial | Completo | Completo + Dossiê exportável |
| SOPs & Quality Management | — | — | Escopo reduzido | Escopo completo |
| Seed-to-Patient Traceability | — | — | — | Completo |
| Member-Patient Registry | Básico | Ampliado | Ampliado | Completo com vínculo estatutário |
| Risk & Pharmacovigilance | — | — | Escopo reduzido | Escopo completo |
| Evidence & Real-World Data Engine | — | — | — | Completo |
| Regulatory Reporting & Audit Trail | — | Parcial | Ampliado | Completo + exportação ANVISA-ready |
| Ancoragem em blockchain pública | — | — | — | Completo |

### 9.3. Novo plano — Sandbox Ready

**Público-alvo:** associações de pacientes que pretendem concorrer ao Edital de Chamamento da ANVISA, ou que operam via autorização judicial e precisam migrar para o regime regulado até agosto de 2027.

**Inclusos:**

- Todos os sete submódulos do SCC em escopo completo.
- Ancoragem em blockchain pública.
- Onboarding de compliance assistido pela equipe da CannabIA.
- Suporte prioritário para submissão ao Edital.
- Dashboards regulatórios dedicados.

**Modelo de precificação sugerido:** combinação de fee recorrente de plataforma + ticket por associado cadastrado + setup de compliance. O detalhamento de valores fica para documento comercial específico.

### 9.4. SKU de consultoria regulatória parceira

A consultoria jurídica é oferecida como **SKU separável**, em duas modalidades:

- **CannabIA Sandbox Ready (Plataforma)** — apenas a plataforma, sem camada jurídica.
- **CannabIA Sandbox Ready + Legal Desk** — plataforma + acesso a rede credenciada de escritórios parceiros especializados em cannabis medicinal e regulação sanitária.

A associação escolhe a modalidade no momento da contratação e pode migrar entre elas a qualquer tempo. A CannabIA pode trabalhar com mais de um escritório parceiro, oferecendo escolha à associação.

---

## 10. Fluxos operacionais principais

Esta seção descreve os fluxos de ponta a ponta que o SCC suporta. Cada fluxo dispara eventos imutáveis de rastreabilidade e auditoria.

### 10.1. Fluxo de ingresso da associação

1. Cadastro inicial com CNPJ, estatuto, corpo diretivo.
2. Validação automática de elegibilidade (natureza jurídica, tempo mínimo).
3. Cadastro do Responsável Técnico e validação de habilitação.
4. Declaração de infraestrutura, equipe, processos e escala proposta.
5. Geração da Matriz de Capacidade Técnico-Operacional.
6. Exportação do Dossiê de Elegibilidade.

### 10.2. Fluxo de preparação do Projeto Experimental

1. Configuração do escopo do projeto no Governance Hub.
2. Geração dos cinco planos obrigatórios a partir de templates parametrizados.
3. Revisão e aprovação interna.
4. Exportação no formato previsto pelo Edital de Chamamento.
5. Submissão à ANVISA.

### 10.3. Fluxo de rastreabilidade seed-to-patient

1. Registro do lote de sementes ou matriz genética.
2. Registro de plantio e identificação individual das plantas.
3. Registro de colheita com laudo analítico associado.
4. Registro de extração com parâmetros de processo.
5. Registro de produção de preparado com laudo analítico.
6. Dispensação a associado regularmente cadastrado com prescrição válida.
7. Cada etapa gera evento imutável com hash encadeado.
8. Ancoragem periódica da raiz Merkle em blockchain pública.

### 10.4. Fluxo de farmacovigilância

1. Captura de evento adverso pelo associado via canal preferencial.
2. Triagem clínica assistida por IA com classificação de severidade.
3. Revisão pelo Responsável Técnico.
4. Notificação automatizada à ANVISA via VigiMed/Notivisa quando aplicável.
5. Registro de desdobramento clínico e evolução.
6. Atualização do dashboard epidemiológico.

### 10.5. Fluxo de encerramento e Parecer Final

1. Compilação dos indicadores obrigatórios ao longo do ciclo.
2. Agregação dos desfechos clínicos e estudos observacionais.
3. Consolidação das evidências de aplicação de SOPs.
4. Consolidação da trilha de auditoria e provas de ancoragem.
5. Geração do Parecer Final de Monitoramento.
6. Submissão à ANVISA como insumo do Relatório Técnico-Regulatório Consolidado.

---

## 11. Governança e auditoria

### 11.1. Princípios

- Toda ação crítica é rastreável até o ator, timestamp e contexto.
- Toda alteração de documento regulatório é versionada.
- Toda decisão de IA é auditável.
- Toda modificação retroativa é impossível na camada de eventos e detectável na camada de contexto.

### 11.2. Escopos de auditoria consolidados

- Auditoria clínica — prescrições, dispensações, desfechos, eventos adversos.
- Auditoria operacional — SOPs executados, desvios, CAPAs.
- Auditoria de qualidade — laudos analíticos, perfis de canabinoides, conformidade de lote.
- Auditoria de segurança — acessos, falhas, alterações sensíveis.
- Auditoria financeira — lançamentos, repasses, contribuições associativas.
- Auditoria de IA — entradas, modelos, saídas, custos, decisões.
- Auditoria regulatória — submissões, respostas, consultas de fiscalização.

### 11.3. Tempo de retenção

A retenção mínima de trilhas de auditoria deve cobrir o ciclo completo do sandbox acrescido de período de contingência pós-encerramento, conforme normas sanitárias aplicáveis e orientação jurídica específica — a ser detalhada em política formal de retenção.

---

## 12. LGPD e pontos não flexibilizáveis

O SCC trata LGPD como camada arquitetural, não como política de operação.

### 12.1. Separação estrutural

- Tabelas de evento de rastreabilidade não contêm PII.
- Tabelas de contexto clínico e cadastral contêm PII e são apagáveis.
- O vínculo entre ambas é feito por identificador, não por conteúdo.
- Ao exercer o direito de apagamento, a associação apaga o contexto sem quebrar a cadeia de eventos.

### 12.2. Consentimento

Consentimento informado é exigido antes de qualquer cadastro de associado e antes de qualquer uso secundário de dados (evidência regulatória, publicação científica).

### 12.3. Compartilhamento com a ANVISA

A RDC impõe obrigação de compartilhamento de dados. O SCC prepara dados em forma **minimamente necessária e pseudonimizada quando possível**, respeitando a finalidade regulatória.

### 12.4. Ancoragem e LGPD

Nenhum dado pessoal, clínico ou operacional é publicado em blockchain pública. A ancoragem usa apenas raízes Merkle — hashes derivados, não reversíveis ao dado original.

---

## 13. Programa piloto e parceria institucional

### 13.1. Piloto-referência

O piloto-referência é construído com uma associação parceira já identificada. O objetivo é:

- Validar o SCC em operação real.
- Produzir caso documentado com métricas.
- Testar o processo de preparação para o Edital.
- Gerar material institucional para a proposta à entidade nacional.

### 13.2. Escopo do piloto

- Implantação completa do SCC no tenant da associação.
- Acompanhamento conjunto por 6 a 12 meses.
- Documentação contínua dos aprendizados.
- Métricas de prontidão regulatória, volume rastreado, eventos capturados e indicadores.

### 13.3. Aproximação com entidade nacional

Em paralelo ao piloto, a proposta institucional para uma entidade nacional representativa das associações (APEPI, ABRACE, ou federação equivalente) é trabalhada com o objetivo de:

- Posicionar a CannabIA como infraestrutura de referência para o ecossistema associativo.
- Estabelecer modelo de credenciamento ou recomendação setorial.
- Criar programa de adesão coletiva com condições especiais para associações-membro.

O detalhamento do piloto e das parcerias institucionais fica para documento subsequente dedicado.

---

## 14. Roadmap sugerido

### Trimestre 1 — Fundação regulatória e documental

- Fechamento deste documento e aprovação interna.
- Leitura jurídica detalhada da RDC 1.014/2026 e normas correlatas.
- Modelagem de dados em nível físico.
- Documento técnico de contratos de API.
- Protótipo do Governance Hub e do SOP Manager.

### Trimestre 2 — Núcleo operacional

- Seed-to-Patient Traceability em produção.
- Member-Patient Registry evoluído.
- Risk & Pharmacovigilance em produção.
- Extensão da auditoria consolidada.

### Trimestre 3 — Inteligência regulatória

- Evidence & Real-World Data Engine em produção.
- Regulatory Reporting com geração automática dos planos obrigatórios.
- Indicators Engine operando em tempo real.
- Ancoragem em blockchain pública operacional.

### Trimestre 4 — Certificação e go-to-market

- Piloto com a associação-parceira.
- Revisão jurídica externa.
- Posicionamento comercial do plano Sandbox Ready.
- Aproximação formal com entidade nacional.
- Alinhamento à versão final do Edital de Chamamento quando publicado.

---

## 15. Riscos e mitigações

### 15.1. Risco de promessa regulatória indevida

O posicionamento comercial deve distinguir **prontidão** (o que a CannabIA entrega) de **aprovação** (prerrogativa exclusiva da ANVISA). A comunicação oficial da plataforma proíbe afirmações do tipo "garante aprovação no sandbox".

### 15.2. Risco de flexibilização indevida de salvaguardas

As três salvaguardas do Art. 17 são invariantes arquiteturais. Nenhuma configuração de tenant, customização white-label ou parametrização comercial pode desligá-las. Essa decisão é registrada como regra arquitetural imutável.

### 15.3. Risco de publicidade indevida

O Plano de Comunicação gerado automaticamente bloqueia conteúdo promocional por design. O Hub de Comunicação do associado opera sob política de moderação regulatória.

### 15.4. Risco de desalinhamento com o Edital

A arquitetura é edital-agnóstica; os parâmetros são edital-adaptáveis. Quando o Edital for publicado, a adaptação é feita via parâmetros governados pela organização-mãe, não via refatoração.

### 15.5. Risco de dependência de provedor de blockchain

A ancoragem usa protocolos abertos (OpenTimestamps) e redes descentralizadas. A dependência é da rede pública, não de um provedor específico.

---

## 16. Pontos para aprofundamento posterior

- Modelagem física detalhada das entidades novas e migrations SQL.
- Contratos de API do SCC com o restante da plataforma.
- Política formal de retenção de dados e anonimização.
- Modelo de cálculo dos indicadores obrigatórios — a ser fechado após publicação do Edital.
- Fluxo detalhado de integração com SNGPC e VigiMed/Notivisa.
- Protocolo de ancoragem em blockchain pública (frequência, rede preferencial, fallback).
- Templates dos cinco planos obrigatórios do Projeto Experimental.
- Matriz detalhada de flexibilizações regulatórias aceitáveis no Protocolo de Adequação Regulatória Experimental.
- Modelo jurídico e comercial da rede de escritórios parceiros.
- Modelo de adesão coletiva para entidade nacional representativa.

---

## 17. Regras aprovadas neste documento

Ficam aprovadas como base oficial do SCC:

- A CannabIA constrói o Sandbox Compliance Core como módulo transversal, não como produto separado.
- O SCC cobre preparação pré-edital, operação durante o sandbox e encerramento com Parecer Final.
- Rastreabilidade, farmacovigilância e proteção de dados são invariantes arquiteturais não configuráveis.
- A rastreabilidade seed-to-patient usa arquitetura híbrida em três camadas: PostgreSQL append-only, cadeia de hashes interna e ancoragem em blockchain pública.
- PII nunca toca blockchain pública. Apenas raízes Merkle são ancoradas.
- SOPs e farmacovigilância em escopo reduzido descem para o plano Premium.
- O plano Sandbox Ready é criado como novo tier acima do Premium.
- A consultoria regulatória parceira é SKU separável, com rede credenciada de escritórios.
- A comunicação comercial distingue rigorosamente prontidão de aprovação regulatória.
- Toda ação crítica é auditável; toda alteração retroativa é impossível na camada de eventos.
- O piloto-referência é construído com associação parceira já identificada.
- A aproximação com entidade nacional é trabalhada em paralelo ao piloto.

---

## 18. Conclusão

O Sandbox Compliance Core posiciona a CannabIA como a infraestrutura operacional, clínica e documental de referência para o ecossistema associativo brasileiro diante do novo marco regulatório da cannabis medicinal.

A estratégia não depende de antecipar o Edital de Chamamento. Ela depende de construir uma arquitetura rigorosa, aderente ao que a RDC 1.014/2026 já estabelece de forma firme, e adaptável ao que o Edital fechará nos meses seguintes.

A combinação de rastreabilidade seed-to-patient com ancoragem em blockchain pública, farmacovigilância estruturada, SOPs vivos com evidência de aplicação, registro de associado regularmente cadastrado, auditoria consolidada e Evidence Engine alimentado pela IA e pela telemetria já existentes é o conjunto que uma associação precisa para ingressar no sandbox com competitividade real.

Este documento estabelece a fundação sobre a qual serão construídos os documentos subsequentes de modelagem técnica, contratos de API, templates regulatórios, programa piloto e parcerias institucionais.
