# 19 — Frontend Strategy

## 1. Objetivo do documento

Formalizar a decisão arquitetural para evolução do frontend da CannabIA, definindo:

- a direção oficial de migração
- o papel de Flask e Next.js na arquitetura alvo
- os princípios de transição para não desperdiçar esforço
- a ordem recomendada de migração em fases

---

## 2. Decisão arquitetural

### Decisão

A CannabIA passará a evoluir para uma arquitetura com:

- **Flask como backend principal**
- **Next.js como frontend principal**

No curto prazo, a aplicação continuará operando com frontend server-rendered em Jinja, mas **novas telas ricas e a evolução visual relevante devem convergir para Next.js**.

### Decisão complementar

- Não vamos reconstruir o sistema inteiro agora
- Não vamos parar a evolução do backend para migrar UI antes da hora
- O frontend atual em Jinja será mantido apenas como camada transitória e operacional
- O investimento pesado em experiência, design system e UX ocorrerá no frontend novo em Next.js

---

## 3. Por que esta decisão foi tomada

### 3.1. Situação atual

Hoje o frontend do projeto:

- é majoritariamente composto por templates Jinja
- usa CSS inline ou embutido nos próprios templates
- possui pouca reutilização estrutural entre telas
- quase não possui camada JavaScript organizada
- não tem design system formal
- não possui pipeline frontend independente

Isso é suficiente para operação inicial, mas insuficiente para a ambição da plataforma.

### 3.2. Problema real observado

O principal incômodo não está no backend Flask em si. O problema atual está na camada de apresentação:

- telas visualmente pobres
- baixa capacidade de evoluir experiência complexa
- dificuldade para construir componentes reutilizáveis
- manutenção frágil de UI
- baixa escalabilidade para timeline, prontuário, acompanhamento, dashboards ricos e fluxos operacionais mais sofisticados

### 3.3. Por que não continuar só com Flask + Jinja

Flask + Jinja é aceitável para:

- painéis simples
- CRUD básico
- telas administrativas pequenas
- protótipos de operação

Mas a CannabIA está caminhando para:

- jornada clínica rica
- prontuário longitudinal
- timeline do paciente
- acompanhamento contínuo
- dashboards operacionais mais densos
- white-label evoluído
- experiência de produto mais sofisticada

Nesse contexto, insistir em Jinja como frontend principal tende a gerar retrabalho.

### 3.4. Por que Next.js e não apenas React puro

React puro resolveria a camada de componentes, mas Next.js traz uma estrutura mais adequada para o que o produto deve virar:

- roteamento e layouts prontos
- organização melhor de aplicação frontend de médio/longo prazo
- base melhor para crescimento do painel
- suporte natural a arquitetura híbrida de telas
- caminho mais claro para expansão futura do produto

Para a CannabIA, isso faz mais sentido do que introduzir apenas uma SPA React sem convenções.

---

## 4. Arquitetura alvo

### 4.1. Papel do Flask

O Flask permanece responsável por:

- autenticação atual
- multi-tenancy e contexto de acesso
- regras de negócio
- serviços clínicos e operacionais
- webhook WhatsApp
- integrações externas
- IA, RAG e auditoria
- acesso ao banco
- APIs JSON para consumo do frontend novo

### 4.2. Papel do Next.js

O Next.js passa a ser responsável por:

- interface principal do produto
- design system e componentes reutilizáveis
- layout e navegação do painel
- experiência de prontuário, timeline, atendimento e acompanhamento
- estado de interface e interações mais ricas
- evolução visual e responsiva da plataforma

### 4.3. Princípio de separação

O frontend em Next.js não deve absorver regra de negócio clínica ou operacional sensível.

Regra de domínio continua no backend.

O frontend:

- consome APIs
- apresenta dados
- coordena interação do usuário
- aplica validações de UX

O backend:

- decide
- valida
- persiste
- audita
- protege

---

## 5. Estratégia de transição

### 5.1. Regra principal

**Não fazer redesign profundo no Jinja atual.**

Daqui em diante:

- corrigimos frontend atual apenas quando necessário para operação
- evitamos grandes refactors visuais em templates Flask
- qualquer investimento estrutural de UI deve mirar o frontend novo

### 5.2. Modelo de convivência

Durante a transição, teremos um modelo híbrido:

- backend Flask continua rodando o sistema atual
- frontend Next.js nasce em aplicação separada
- as telas novas entram aos poucos
- o frontend legado permanece como fallback operacional até a migração das áreas críticas

### 5.3. Estratégia de entrada

A recomendação é criar o frontend novo em uma pasta própria:

```text
frontend/
```

E iniciar a migração por rotas de painel autenticado.

---

## 6. Fases da migração

## Fase 0 — Congelamento estratégico do frontend legado

### Objetivo

Parar de investir onde haverá descarte posterior.

### Diretrizes

- não criar novas telas complexas em Jinja
- não criar novo design system no Flask
- não espalhar mais CSS inline além do estritamente necessário
- manter o frontend atual funcional até a entrada da nova camada

### Entregáveis

- este documento
- alinhamento do time sobre Next.js como direção oficial

---

## Fase 1 — Preparação do backend para consumo por frontend externo

### Objetivo

Transformar o backend em uma base confiável para UI desacoplada.

### O que precisa existir

- endpoints JSON consistentes
- padronização de erros
- autenticação utilizável pelo frontend novo
- leitura do contexto do usuário autenticado
- leitura do contexto de tenant/clinic
- contratos estáveis para módulos principais

### APIs prioritárias

1. sessão e autenticação
2. dashboard
3. atendimentos
4. detalhe do atendimento
5. timeline do paciente
6. prontuário longitudinal
7. agendamentos

### Resultado esperado

O backend Flask passa a servir tanto o frontend legado quanto o frontend novo.

---

## Fase 2 — Bootstrap do projeto Next.js

### Objetivo

Criar a fundação real do novo frontend.

### Decisões recomendadas

- Next.js com App Router
- TypeScript
- aplicação independente em `frontend/`
- consumo de API do backend Flask por HTTP
- camada de cliente de API centralizada
- design tokens e componentes compartilháveis desde o início

### Estrutura inicial sugerida

```text
frontend/
├── app/
├── components/
├── lib/
├── styles/
├── public/
├── package.json
└── tsconfig.json
```

### Entregáveis

- app Next.js inicial rodando
- layout base autenticado
- configuração de ambiente
- cliente HTTP para integração com Flask

---

## Fase 3 — Migração das primeiras telas críticas

### Ordem recomendada

1. login e shell autenticado
2. dashboard
3. lista de atendimentos
4. detalhe do atendimento
5. timeline do paciente
6. prontuário longitudinal
7. agendamento

### Motivo

Essas telas são as que mais se beneficiam de:

- melhor organização visual
- componentes reutilizáveis
- estado de interface
- UX clínica mais densa

### Resultado esperado

O coração operacional da plataforma passa a viver no frontend novo.

---

## Fase 4 — Convivência híbrida controlada

### Objetivo

Operar com dois frontends sem caos.

### Regras

- Next.js recebe prioridade para telas novas
- Flask/Jinja mantém rotas legadas ainda não migradas
- documentação deve apontar claramente o que já migrou
- não duplicar lógica de negócio entre as duas camadas

### Resultado esperado

Transição gradual, com baixo risco operacional.

---

## Fase 5 — Consolidação do frontend principal

### Objetivo

Transformar o Next.js no frontend padrão do produto.

### Ações

- migrar rotas restantes de painel
- reduzir dependência de templates Jinja
- manter no Flask apenas backend, auth, APIs, webhooks e páginas técnicas mínimas quando necessário

### Resultado esperado

Flask deixa de ser a camada principal de interface e passa a ser a espinha de serviços e domínio.

---

## 7. Priorização de telas para o novo frontend

| Prioridade | Área | Motivo |
|-----------|------|--------|
| Muito alta | Atendimento detalhado | maior densidade clínica e operacional |
| Muito alta | Timeline do paciente | experiência rica e longitudinal |
| Muito alta | Prontuário | precisa de componentes, estados e navegação melhores |
| Alta | Dashboard | melhora visual e leitura operacional |
| Alta | Agendamento | fluxo frequente e simples de migrar |
| Média | Histórico de mensagens | pode evoluir depois |
| Média | Realtime | depende da estratégia final de socket/UI |
| Baixa | Páginas técnicas auxiliares | pouco impacto de produto |

---

## 8. Regras de implementação durante a transição

### Fazer

- tratar Flask como backend de domínio
- construir APIs estáveis
- documentar contratos entre frontend e backend
- padronizar payloads JSON
- priorizar componentes reutilizáveis no Next.js
- pensar em design system desde o início

### Não fazer

- reescrever backend por causa da troca de frontend
- duplicar validação sensível do backend no frontend
- investir pesado em estética de templates legados
- criar telas complexas novas em Jinja
- migrar tudo de uma vez

---

## 9. Riscos e cuidados

### Risco 1 — Tentar migrar tudo de uma vez

Isso tende a travar o produto e atrasar tanto backend quanto frontend.

### Risco 2 — Misturar responsabilidade entre Next.js e Flask

Se o frontend começar a carregar regra de domínio demais, a base ficará inconsistente.

### Risco 3 — Fazer frontend novo sem contratos de API

Sem endpoints estáveis, a migração vira improviso.

### Risco 4 — Continuar investindo em Jinja como se fosse definitivo

Isso consome tempo em uma camada que já está marcada para transição.

---

## 10. Decisão operacional imediata

A partir deste documento:

- seguimos evoluindo backend, domínio e estrutura atual
- evitamos grandes investimentos de UI no Jinja
- preparamos o backend para APIs
- planejamos a criação do `frontend/` em Next.js como próxima frente relevante de produto

---

## 11. Próximos passos recomendados

1. Criar documento técnico de contratos de API para o frontend novo
2. Definir estratégia de autenticação entre Next.js e Flask
3. Criar backlog técnico da fase de bootstrap do `frontend/`
4. Iniciar o projeto Next.js em pasta separada
5. Migrar primeiro o detalhe do atendimento, timeline e prontuário

---

## 12. Referências oficiais

- React recomenda adoção incremental em projetos existentes e, quando uma área inteira da UI passa a ser React, o uso de framework React se torna o caminho natural
- Next.js é a escolha para estruturar esse frontend novo com roteamento, layouts e organização de aplicação

Referências:

- https://react.dev/learn/add-react-to-an-existing-project
- https://nextjs.org/docs
- https://nextjs.org/docs/app
