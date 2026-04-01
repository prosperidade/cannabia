# 10 — Segurança, Compliance e Auditoria

## 1. Propósito do documento

Este documento define a base de **segurança, compliance, governança de acesso e auditoria** da plataforma CannabIA, considerando a implementação já existente e as adaptações necessárias para uma operação robusta, multi-tenant, auditável e regulatoriamente defensável.

---

## 2. Cinco pilares de segurança da CannabIA

```
1. Isolamento por tenant
2. Controle rigoroso de acesso
3. Proteção de dados sensíveis
4. Auditabilidade ponta a ponta
5. Governança de integrações e IA
```

---

## 3. Princípios centrais

| Princípio | Descrição |
|-----------|-----------|
| **Menor privilégio** | Todo usuário/componente acessa apenas o mínimo necessário |
| **Contexto explícito** | Nenhuma operação sensível ocorre sem contexto claro de tenant/usuário |
| **Responsabilidade clínica humana** | A plataforma assiste, nunca substitui a responsabilidade médica |
| **Auditabilidade por padrão** | Toda ação relevante deve poder ser rastreada |
| **Segurança em camadas** | Proteção em: autenticação, autorização, aplicação, dados, integrações, IA |
| **Evolução sem ruptura** | Segurança cresce junto com a evolução da base atual |

---

## 4. Segurança multi-tenant

**Regra obrigatória:** nenhuma consulta, mutação, leitura de prontuário, execução de automação ou uso de integração sensível pode ignorar o escopo do tenant.

Isso vale para: pacientes, atendimentos, mensagens, prontuários, alertas, documentos, pagamentos, configurações, integrações e execuções de IA.

### Estratégia de adaptação

```
Estado atual:  isolamento por clinic_id
Direção futura: isolamento por tenant_id
Estratégia:    expandir progressivamente, preservar clinic_id onde ainda funciona
```

---

## 5. Autenticação

### Estado atual

- Flask-Login implementado
- Autenticação por usuário e senha
- Sessão com controle de acesso

### Direção recomendada

- Usuários com múltiplos vínculos a tenants
- Contexto de tenant ativo na sessão
- Trilha de login e logout
- Possibilidade futura de 2FA para perfis sensíveis

### Regras mínimas

- Identificação inequívoca do usuário
- Sessão segura com controle de expiração
- Invalidação adequada de sessão
- Rastreio de falhas de login
- Limitação de tentativas quando aplicável

---

## 6. Autorização e perfis

### Modelo adotado

```
RBAC + Escopo por tenant + Restrição clínica por responsabilidade
```

### Perfis de maior criticidade

- Super Admin da Organização
- Admin do Tenant
- Médico

### Perfis com acesso limitado

- Agente de atendimento
- Agente de acompanhamento
- Paciente

### Regras de visibilidade

| Regra | Descrição |
|-------|-----------|
| Prontuário | Restrito ao médico e admin com política clínica |
| Dados financeiros | Restrito ao admin e billing |
| Credenciais/integrações | Restrito ao admin do tenant |
| Dados entre tenants | Bloqueado por padrão |

---

## 7. Proteção de dados clínicos

A CannabIA lida com dados de saúde, exigindo:

- Acesso clínico controlado por perfil e tenant
- Controle de acesso explícito a documentos clínicos
- Logs clínicos sensíveis auditáveis
- Alterações relevantes rastreadas
- Distinção entre visualização e edição na auditoria

---

## 8. LGPD e governança de consentimento

**Direções obrigatórias:**

- Definir base legal para cada tipo de tratamento
- Separar uso clínico, operacional e comercial
- Registrar consentimentos quando aplicável
- Controlar e limitar compartilhamento
- Permitir rastreabilidade de uso de dados

**Pontos a detalhar em documento específico:**

- Consentimento do paciente
- Compartilhamento entre tenants
- Uso de dados anonimizados
- Política de retenção e exclusão

---

## 9. Segurança de documentos e anexos

**Requisitos mínimos:**

- Armazenamento seguro com vínculo a tenant e paciente
- Controle de acesso por perfil
- Rastreio de upload e visualização
- Prevenção de acesso indevido entre tenants

---

## 10. Segurança de credenciais por tenant

A configuração de chave de API de IA por tenant é um ponto crítico de segurança.

**Requisitos:**

- Armazenamento criptografado
- Nunca exibir a chave em texto puro após cadastro
- Trilha de alteração de credencial
- Separação total por tenant
- Validação segura de uso

**Regra geral para todas as credenciais:**

```
Não versionar em código
Segregar por ambiente e por tenant
Rastrear toda alteração sensível
Limitar quem pode editar ou visualizar
```

---

## 11. Segurança no uso da IA

**Riscos principais:**

- Prompt injection
- Uso de contexto de tenant incorreto
- Mistura indevida de dados entre tenants
- Saída excessivamente confiante
- Exposição acidental de dados sensíveis em prompts ou outputs

**Direções obrigatórias:**

- Validação de entrada e limitação de escopo
- Versionamento de prompts e logs de execução
- Rastreabilidade do contexto usado
- Revisão humana para decisões clínicas finais

---

## 12. Auditoria de IA

*Base já existente — preservar e expandir.*

Registrar por execução:

```
tenant_id, paciente_relacionado, usuario_relacionado,
tipo_de_uso, entrada, saida, modelo_utilizado,
prompt_ou_versao, custo_estimado, horario,
status_execucao, erro_se_houver
```

---

## 13. Auditoria clínica

Eventos que exigem trilha clínica:

| Evento | Auditável |
|-------|----------|
| Criação/alteração de prontuário | ✅ |
| Registro de consulta | ✅ |
| Ajuste de dose | ✅ |
| Solicitação de exame | ✅ |
| Alteração de plano terapêutico | ✅ |
| Escalonamento de alerta | ✅ |

**Cada evento deve responder:**
- Quem realizou, quando, em qual tenant, sobre qual paciente
- Qual foi a ação, estado anterior (quando aplicável), desfecho

---

## 14. Auditoria operacional

Cobrir: acolhimento, triagem, envio de QR Code, agendamento, notificações, questionários, transbordo para humano, mudanças de estado da jornada.

---

## 15. Auditoria financeira

Cobrir: cobrança gerada, QR Code emitido, status do pagamento (confirmação, expiração, falha), liberação de jornada, evolução do plano comercial.

---

## 16. Auditoria de segurança

Registrar: tentativas de login inválidas, acessos negados, alteração de credenciais, troca de configuração sensível, falhas de autorização, ações administrativas críticas.

---

## 17. Observabilidade técnica

**Direção futura:**

- Logs estruturados e métricas por módulo
- Alertas técnicos de falha
- Rastreamento de incidentes
- Visibilidade por tenant

---

## 18. Separação por ambiente

| Ambiente | Regra |
|---------|-------|
| Desenvolvimento | Credenciais distintas |
| Homologação | Dados de produção protegidos |
| Produção | Configurações mais rígidas; logs preservados |

---

## 19. Estratégia de adaptação da base atual

| Ação | Escopo |
|------|--------|
| **Reaproveitar** | Autenticação, controle de tenant por clínica, rate limiting, auditoria de IA, documentação de segurança existente |
| **Adaptar** | Tenancy clinic_id → tenant_id; RBAC ampliado; proteção de credenciais por tenant |
| **Criar** | Auditoria clínica e financeira estruturada; eventos de segurança; política formal de segredos; LGPD formalizada; consentimento e retenção |

---

## 20. Regras aprovadas neste documento

- Segurança é pilar central da CannabIA
- Tenant é unidade obrigatória de isolamento
- Controle de acesso via RBAC com escopo por tenant
- Dados clínicos exigem governança reforçada
- Integrações devem ser auditáveis
- Chaves de IA por tenant exigem proteção especial
- IA opera com limites, rastreabilidade e segurança
- Eventos clínicos, financeiros, operacionais e de segurança são auditáveis
- A base existente será evoluída, não descartada
- LGPD orienta a governança dos dados da plataforma

---

## 21. Pontos para aprofundamento posterior

- Política formal de consentimento
- Política de retenção de dados e anonimização
- Matriz formal de acesso por ação
- Plano de resposta a incidentes
- Requisitos de criptografia em repouso e em trânsito
- Política de backups e recuperação
- Trilha de acesso a documentos clínicos
- Revisão regulatória específica do domínio cannabis medicinal

---

## 22. Conclusão

A CannabIA já possui base concreta de autenticação, tenancy e auditoria. A nova fase exige consolidar essas capacidades em uma arquitetura de segurança mais formal, abrangente e preparada para escala.

O caminho é ampliar com método o que já existe — garantindo proteção de dados, isolamento adequado, controle de acesso, governança de integrações e rastreabilidade completa.
