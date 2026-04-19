# 26 — Protocolo de Ancoragem em Blockchain Pública

## 1. Propósito do documento

Este documento especifica em profundidade a **Camada 3 da estratégia de imutabilidade** da CannabIA, definida conceitualmente na Seção 6 do `23_SANDBOX_COMPLIANCE_CORE.md`: o **Protocolo de Ancoragem em Blockchain Pública**.

Ele cobre:

- Fundamentos criptográficos (Merkle trees, provas de inclusão).
- Escolha de redes blockchain e racional por trás dela.
- Cadência e escopo das ancoragens.
- Fluxo operacional de geração, submissão e verificação.
- Tratamento de falhas, retry, reorgs e outros cenários de exceção.
- Custos e orçamento esperado.
- Interface de verificação pública.
- Estratégia de migração, fallback e sucessão de redes.

O objetivo é que este documento sirva como especificação suficientemente precisa para o time de engenharia implementar o protocolo de forma robusta, auditável e LGPD-conforme.

---

## 2. Fundamentos da escolha

### 2.1. O problema a resolver

A RDC 1.014/2026 e as normas correlatas exigem rastreabilidade **imutável e auditável**. Três níveis de ataque devem ser impossíveis:

- Alteração retroativa de um evento passado.
- Inserção retroativa de evento forjado na linha temporal.
- Deleção ou reordenação de eventos.

As Camadas 1 e 2 da arquitetura (PostgreSQL append-only + hash chaining interno) protegem contra ataques externos e contra erros operacionais. Não protegem contra um ataque interno com privilégio máximo (administrador do banco de dados capaz de reescrever histórico, inclusive os hashes).

A Camada 3 resolve exatamente esse cenário: ancorar hashes em uma rede pública torna computacionalmente inviável a reescrita coordenada, porque a reescrita precisaria refazer o histórico da blockchain pública também — o que está fora do controle da CannabIA, da associação e de qualquer ator malicioso isolado.

### 2.2. Por que não blockchain como banco operacional

Registrado em `23_SANDBOX_COMPLIANCE_CORE.md`, Seção 6.2. Os três motivos: conflito com LGPD, custo e complexidade, e não-exigência regulatória. Este documento reforça a decisão: blockchain é usada **exclusivamente** para ancoragem de provas derivadas, nunca para armazenar dados em si.

### 2.3. Por que Merkle tree

Merkle tree é a estrutura que permite ancorar **milhões de eventos em uma única transação**, mantendo a capacidade de provar individualmente que cada evento estava incluído no conjunto ancorado. Isso é o que torna o protocolo economicamente viável.

- A raiz Merkle é um único hash de 32 bytes.
- Cada evento gera uma prova de inclusão (Merkle path) de tamanho logarítmico.
- A verificação de um evento individual usa apenas a prova e a raiz — ninguém precisa baixar todo o conjunto.

---

## 3. Redes escolhidas

A ancoragem usa duas redes em paralelo, com papéis complementares.

### 3.1. Bitcoin via OpenTimestamps (OTS) — âncora primária de longo prazo

**Racional:** Bitcoin é a blockchain pública com maior descentralização, maior hashrate de segurança e maior longevidade comprovada. OpenTimestamps é um protocolo aberto e gratuito que agrega milhares de hashes de diferentes clientes em uma única transação no Bitcoin, amortizando o custo a praticamente zero para o usuário final.

**Uso no protocolo:** toda raiz Merkle é submetida ao OTS. A prova resultante (arquivo `.ots`) é o **registro canônico de longo prazo**.

**Cadência:** diária.

**Custo direto:** zero. O OTS é operado por calendar servers públicos e gratuitos.

**Latência:** a submissão é imediata, mas a confirmação no Bitcoin pode levar algumas horas. Essa é a principal limitação e motiva o uso simultâneo da segunda rede.

### 3.2. Polygon (PoS) — âncora secundária de verificação rápida

**Racional:** Polygon oferece finalidade rápida (minutos), custos muito baixos (centavos por transação) e é amplamente usada em aplicações empresariais que precisam de blockchain pública auditável sem o peso operacional do Ethereum mainnet.

**Uso no protocolo:** toda raiz Merkle é também registrada em um smart contract simples em Polygon, que armazena `(tenant_id, covered_period, merkle_root, anchor_timestamp)` e emite um evento verificável.

**Cadência:** diária, em paralelo ao OTS.

**Custo direto:** centavos a poucos reais por ancoragem dependendo da congestão da rede.

**Latência:** minutos entre submissão e confirmação.

### 3.3. Por que duas redes

- **Redundância.** Se uma rede tiver problema pontual (congestionamento, bug de cliente, incidente de governança), a outra continua operando.
- **Complementaridade de latência.** Polygon dá confirmação rápida útil no dia a dia; Bitcoin dá garantia histórica de décadas.
- **Complementaridade de custo.** OTS é gratuito mas lento; Polygon é barato e rápido.
- **Complementaridade de auditoria.** Um auditor pode verificar a prova na rede que preferir; se uma levantar suspeita, a outra serve de contraprova.

### 3.4. Ethereum mainnet como opção futura

Para associações ou projetos experimentais específicos que exijam ancoragem de altíssimo perfil (ex.: relatório final do ciclo completo do sandbox, publicação científica), o protocolo prevê a possibilidade de ancorar adicionalmente em Ethereum mainnet. Essa ancoragem é opcional, configurada por política, e assumida como opção premium pelo custo significativamente maior por transação.

---

## 4. Escopo das ancoragens

O protocolo define três escopos de ancoragem, operando em paralelo.

### 4.1. Escopo `tenant`

Cada tenant tem sua própria cadeia de eventos. A raiz Merkle dos eventos novos de um tenant desde a última ancoragem é ancorada separadamente.

**Benefício:** cada associação tem prova criptográfica independente de que sua rastreabilidade é íntegra.

**Cadência:** diária para tenants do plano Sandbox Ready.

### 4.2. Escopo `project`

Durante um Projeto Experimental aprovado pela ANVISA, ancoragens específicas são geradas para o conjunto de eventos vinculados àquele projeto, separadamente da cadeia geral do tenant.

**Benefício:** o Parecer Final de Monitoramento e o Relatório Técnico-Regulatório Consolidado podem apontar para ancoragens específicas do período do projeto.

**Cadência:** semanal ou mensal conforme definido no Protocolo de Adequação Regulatória Experimental.

### 4.3. Escopo `global`

A CannabIA mantém uma raiz Merkle agregada de todas as raízes Merkle de todos os tenants e projetos do dia. Esta meta-raiz é ancorada publicamente e atesta que o conjunto consolidado da plataforma é íntegro.

**Benefício:** permite verificação agregada e posicionamento institucional ("toda a operação da CannabIA está ancorada publicamente todos os dias").

**Cadência:** diária.

---

## 5. Fluxo operacional

### 5.1. Fase 1 — Coleta e ordenação

1. O serviço de ancoragem identifica todos os eventos elegíveis desde a última ancoragem bem-sucedida do escopo.
2. Eventos são ordenados por `(chain_id, chain_sequence)` em ordem estável.
3. Cada evento é representado pelo seu `event_hash` já calculado na Camada 2.

### 5.2. Fase 2 — Construção da Merkle tree

1. O conjunto ordenado de hashes forma as folhas da árvore.
2. A árvore é construída por pares, com `SHA-256` em cada nível.
3. Quando o número de folhas em um nível é ímpar, a última folha é duplicada para formar o par (convenção padrão do Bitcoin).
4. O resultado é a raiz Merkle (`merkle_root`) de 32 bytes.

### 5.3. Fase 3 — Submissão às redes

**OTS (Bitcoin):**

1. Criar cliente OTS local apontando para calendar servers públicos e, opcionalmente, para um calendar server próprio da CannabIA para maior controle.
2. Submeter a raiz Merkle: `ots stamp <merkle_root>`.
3. Receber arquivo de prova inicial `.ots`.
4. Armazenar o arquivo em `blockchain_anchors.proof_uri`.
5. Agendar tarefa de upgrade da prova em 24 horas para incluir a confirmação em bloco Bitcoin.

**Polygon:**

1. Usando carteira operacional da CannabIA (com chaves protegidas em cofre de segredos), chamar o smart contract `SandboxAnchor.anchor(scope, scope_id, merkle_root, period_start, period_end)`.
2. Aguardar confirmação de pelo menos 10 blocos.
3. Armazenar `transaction_id`, `block_number`, `block_timestamp` em `blockchain_anchors`.

### 5.4. Fase 4 — Persistência e mapeamento

1. Para cada evento incluído na ancoragem, gerar e armazenar a prova de inclusão (Merkle path) em `anchor_event_mappings`.
2. Atualizar `blockchain_anchors.verification_status` para `confirmed` após confirmações em ambas as redes.
3. Registrar evento de auditoria com toda a metadata da ancoragem.

### 5.5. Fase 5 — Verificação agendada

1. Tarefa diária percorre ancoragens dos últimos 7 dias e revalida:
   - A prova OTS ainda é válida e aponta para bloco Bitcoin conhecido.
   - A transação Polygon ainda existe e aponta para a mesma raiz.
   - Os eventos cobertos, se recalculados a partir do banco, produzem a mesma raiz Merkle.
2. Discrepâncias geram alerta crítico para o time de segurança.

---

## 6. Smart contract Polygon — especificação

Contrato minimalista, imutável (sem função de upgrade), sem estado mutável além do mapeamento de ancoragens.

### 6.1. Interface pública

```
function anchor(
    string calldata scope,
    string calldata scopeId,
    bytes32 merkleRoot,
    uint256 periodStart,
    uint256 periodEnd
) external returns (uint256 anchorId);

function getAnchor(uint256 anchorId)
    external view returns (
        string memory scope,
        string memory scopeId,
        bytes32 merkleRoot,
        uint256 periodStart,
        uint256 periodEnd,
        address submitter,
        uint256 blockTimestamp
    );

function verifyInclusion(
    uint256 anchorId,
    bytes32 eventHash,
    bytes32[] calldata merklePath
) external view returns (bool);

event Anchored(
    uint256 indexed anchorId,
    string scope,
    string scopeId,
    bytes32 merkleRoot,
    uint256 periodStart,
    uint256 periodEnd,
    address indexed submitter
);
```

### 6.2. Propriedades do contrato

- **Imutável.** Sem `selfdestruct`, sem proxy, sem upgrade authority.
- **Append-only.** Ancoragens nunca podem ser alteradas ou removidas.
- **Público.** Qualquer endereço pode ler. Escrita é restrita por lista de submitters autorizados (carteiras operacionais da CannabIA).
- **Auditável.** O código-fonte é verificado em Polygonscan e publicado no repositório da CannabIA.

### 6.3. Gestão de chaves

- Carteira operacional principal usa HSM ou Key Management Service gerenciado.
- Carteira de backup em cofre offline para uso em caso de comprometimento da principal.
- Rotação periódica, documentada.
- Nunca commitadas em código, nunca em variáveis de ambiente em texto claro.

---

## 7. Tratamento de falhas e exceções

### 7.1. Falha na submissão OTS

- Retry exponencial até 5 tentativas.
- Após falhas, registrar estado `pending` em `blockchain_anchors` com tag de erro.
- Job noturno tenta novamente as pendências.
- Alerta se pendência durar mais de 48 horas.

### 7.2. Falha na submissão Polygon

- Retry com ajuste de gas caso a falha seja por underpriced.
- Se falha persistir, verificar congestionamento da rede.
- Fallback: usar segunda carteira operacional.
- Alerta crítico se falha persistir por mais de 1 hora.

### 7.3. Reorg em Polygon

- Polygon pode ter reorgs raros. Por isso o protocolo aguarda 10 blocos antes de marcar como `confirmed`.
- Se uma ancoragem já marcada como confirmada for removida por reorg (evento extremamente improvável mas teoricamente possível), o serviço detecta na verificação diária e reexecuta a ancoragem, registrando ambas no histórico.

### 7.4. Falha do calendar server OTS

- Usar múltiplos calendar servers simultaneamente para redundância.
- Em caso de falha total dos servidores públicos, CannabIA pode operar calendar server próprio.

### 7.5. Indisponibilidade prolongada de rede

Em cenário de indisponibilidade prolongada de uma das redes:

- A outra rede continua ancorando normalmente.
- Uma fila de ancoragens pendentes acumula para a rede indisponível.
- Quando a rede volta, a fila é processada em lote.
- O Parecer Final e o material regulatório apontam para a rede disponível e, quando a outra volta, a prova é atualizada.

### 7.6. Divergência entre redes

Se Polygon e OTS apontarem para raízes Merkle diferentes para o mesmo período e escopo — o que só pode acontecer por bug no serviço de ancoragem:

- Alerta crítico imediato.
- Ancoragem suspensa até investigação.
- Auditoria completa das últimas 48 horas de eventos.
- Resolução manual documentada.

---

## 8. Interface de verificação pública

### 8.1. Endpoint de verificação

A CannabIA expõe endpoint público `/api/v1/verify` que recebe:

- `event_id` e `event_table`, ou
- `event_hash` direto.

Retorna:

- A ancoragem ou ancoragens que cobrem o evento.
- A prova de inclusão (Merkle path).
- Transaction IDs em Polygon e OTS.
- Links para blockexplorers públicos.

O verificador pode usar esse retorno e validar independentemente sem precisar confiar na CannabIA.

### 8.2. Ferramenta de linha de comando

Cliente CLI open-source fornecido pela CannabIA permite a qualquer pessoa:

- Baixar a prova de um evento a partir de um QR Code ou ID.
- Verificar localmente a prova contra Polygon.
- Verificar localmente a prova OTS contra um nó Bitcoin próprio ou via API pública.
- Confirmar que o evento estava no conjunto ancorado na data indicada.

Esse é o ponto-chave do posicionamento: **nenhum ator precisa confiar na CannabIA para verificar a integridade**. A verificação é feita contra redes públicas independentes.

### 8.3. QR Code de verificação pública

Rótulos de preparados e documentos regulatórios carregam QR Code que aponta para a página pública de verificação. Qualquer fiscal, paciente ou auditor pode escanear e confirmar que:

- O lote existe.
- O laudo analítico é o declarado.
- A dispensação ao associado ocorreu na data informada.
- Todos esses eventos estão ancorados em blockchain pública desde a data X.

---

## 9. Custos esperados

Estimativa para uma associação operando no plano Sandbox Ready, com volume médio de 300 associados ativos e operação diária.

| Item | Custo estimado mensal |
|---|---|
| Ancoragens diárias em Polygon (30/mês, escopo tenant) | R$ 15 a R$ 60 |
| Ancoragens OTS | R$ 0 |
| Ancoragem global diária da CannabIA (rateada por tenant) | R$ 5 a R$ 20 |
| Operação do calendar server próprio (opcional) | R$ 50 a R$ 150 |
| Custódia de chaves em KMS gerenciado | R$ 30 a R$ 100 |
| Monitoramento e alertas | incluído na observabilidade geral |
| **Total mensal por tenant Sandbox Ready** | **R$ 50 a R$ 330** |

Esses custos são absorvidos pela fee recorrente do plano Sandbox Ready, sem repasse variável ao tenant.

Para ancoragens adicionais em Ethereum mainnet (opção premium), o custo por transação varia com o gás da rede e pode ficar na faixa de R$ 50 a R$ 300 por ancoragem.

---

## 10. Governança do protocolo

### 10.1. Alterações de protocolo

Qualquer mudança no protocolo que afete a interoperabilidade da verificação (ex.: mudança de algoritmo de hash, estrutura da Merkle tree, formato da prova) passa por:

- Avaliação de impacto documentada.
- Período de comunicação prévia a todos os tenants.
- Manutenção de compatibilidade retroativa com provas antigas — provas antigas continuam válidas com o algoritmo antigo.
- Registro público da transição.

### 10.2. Auditoria externa

Recomenda-se auditoria externa do serviço de ancoragem e do smart contract Polygon antes de o plano Sandbox Ready entrar em produção comercial. O escopo mínimo:

- Revisão do smart contract por firma especializada em segurança.
- Revisão do serviço de ancoragem pelo mesmo ou outro fornecedor.
- Emissão de relatório público de auditoria.

### 10.3. Transparência do código

O smart contract Polygon e o cliente CLI de verificação são publicados como open-source. O serviço de ancoragem em si pode permanecer proprietário, mas as especificações do protocolo e os formatos de prova são públicos, permitindo implementações independentes.

---

## 11. Migração e sucessão de redes

### 11.1. Obsolescência de rede

Se, em horizonte de anos, Polygon deixar de ser operacionalmente viável ou sofrer depreciação, o protocolo prevê migração para rede sucessora:

- Nova rede é adicionada ao conjunto ativo sem remover a antiga.
- Ancoragens novas passam a usar a rede sucessora.
- Ancoragens históricas continuam verificáveis na rede antiga enquanto ela existir.
- Quando a rede antiga se tornar inverificável, a credibilidade das ancoragens históricas passa a depender exclusivamente da âncora Bitcoin via OTS — que justamente por isso foi escolhida como âncora de longo prazo.

### 11.2. Preservação de longo prazo

Para garantir que provas geradas hoje continuem verificáveis daqui a 10 ou 20 anos:

- A âncora Bitcoin via OTS é o mecanismo primário de preservação, pois Bitcoin tem compromisso de compatibilidade histórica extremamente forte.
- A CannabIA mantém arquivo offline dos dados necessários à verificação (provas Merkle, raízes, metadados) independentemente da continuidade da plataforma.
- Em caso de descontinuidade da CannabIA, esses arquivos podem ser publicados para que as associações e a ANVISA verifiquem os registros históricos.

### 11.3. Portabilidade

Se uma associação sair da CannabIA, ela pode exportar todo o seu histórico de eventos e provas. A verificação continua possível contra as redes públicas, independentemente da plataforma que a associação passe a usar.

---

## 12. Papéis e responsabilidades

| Papel | Responsabilidades |
|---|---|
| **Serviço de ancoragem (automatizado)** | Coletar eventos, construir Merkle tree, submeter às redes, persistir provas, verificar diariamente |
| **Time de engenharia** | Manter o serviço, atualizar smart contracts quando necessário, responder a alertas |
| **Time de segurança** | Gerir chaves, revisar alertas críticos, conduzir investigações em caso de divergência |
| **Time de compliance** | Gerar relatórios regulatórios que referenciem ancoragens, responder a fiscalizações |
| **Associação (tenant)** | Operar a plataforma normalmente; o protocolo opera em background sem ação manual |
| **Auditor externo (ANVISA, fiscal, paciente)** | Usar interface pública de verificação para validar ancoragens |

---

## 13. Pontos para aprofundamento posterior

- Especificação completa do smart contract Polygon com testes unitários.
- Critérios de seleção e avaliação de calendar servers OTS.
- Política detalhada de rotação de chaves operacionais.
- SLA interno do serviço de ancoragem.
- Modelo de monitoramento e alertas com thresholds específicos.
- Plano de resposta a incidentes específico do protocolo de ancoragem.
- Documentação do cliente CLI de verificação com exemplos de uso.
- Procedimento de migração entre versões do protocolo quando aplicável.

---

## 14. Regras aprovadas neste documento

Ficam aprovadas como base oficial:

- A ancoragem usa Bitcoin via OpenTimestamps como âncora primária de longo prazo.
- A ancoragem usa Polygon como âncora secundária de verificação rápida.
- Nenhum dado pessoal, clínico ou operacional é exposto publicamente — apenas raízes Merkle.
- A cadência diária é padrão para tenants Sandbox Ready.
- Três escopos coexistem: tenant, project e global.
- Smart contract em Polygon é imutável, append-only e verificado publicamente.
- Provas de inclusão são persistidas em `anchor_event_mappings` para cada evento coberto.
- Verificação diária detecta e alerta divergências entre redes ou inconsistências locais.
- Interface pública de verificação permite auditoria independente por qualquer ator.
- O cliente CLI e o código do smart contract são open-source; o serviço de ancoragem pode ser proprietário.
- Custo da ancoragem é absorvido pela fee recorrente do plano Sandbox Ready.
- Auditoria externa é recomendada antes da entrada em produção comercial.

---

## 15. Conclusão

O Protocolo de Ancoragem em Blockchain Pública é a Camada 3 que transforma a rastreabilidade da CannabIA de "auditável internamente" em **verificável publicamente e independente de qualquer autoridade central**.

A combinação de Bitcoin via OTS (longevidade) com Polygon (rapidez e acessibilidade), o uso de Merkle trees para amortizar custos, o smart contract imutável e a interface pública de verificação criam uma infraestrutura de prova criptográfica que:

- Supera o exigido pela RDC 1.014/2026.
- Oferece diferencial competitivo concreto perante qualquer outro sistema de gestão associativa.
- Respeita integralmente a LGPD.
- Sustenta-se em custos viáveis ao modelo comercial da plataforma.
- Preserva a verificabilidade no horizonte de décadas.

Este documento, combinado ao `22` e ao `24`, completa a especificação técnica da rastreabilidade da CannabIA. O documento seguinte trata da Biblioteca de Templates Regulatórios, fechando o conjunto fundacional da linha SCC.
