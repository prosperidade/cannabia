# 17 — Plano de Migração de `clinic_id` para `tenant_id`

## 1. Propósito do documento

Este documento define a estratégia técnica inicial de transição do modelo atual centrado em `clinic_id` para o modelo amplo centrado em `tenant_id`, preservando compatibilidade com a operação existente.

---

## 2. Premissa central

A CannabIA ainda opera hoje com isolamento efetivo por clínica.

O objetivo desta migração não é remover `clinic_id` imediatamente, mas:

- introduzir `tenant_id` de forma aditiva
- manter o sistema funcionando durante a transição
- permitir evolução progressiva das próximas fases

---

## 3. Estado atual

Hoje o modelo vigente é:

```text
users
  ↕
user_clinics
  ↕
clinics
  ↕
patients / appointments / messages / alerts / monitoring / ai_audit_logs
```

O sistema assume que:

- clínica é a unidade de isolamento
- contexto ativo da sessão é `active_clinic_id`
- permissões por vínculo local ainda dependem de `user_clinics`

---

## 4. Estado alvo de transição

O estado alvo intermediário da próxima fase é:

```text
tenant_types
  ↕
tenants
  ↕
clinics

users
  ↕
user_tenant_roles

compatibilidade temporária:
user_clinics -> clinics -> tenants
```

Neste estágio:

- `clinic_id` continua existindo
- `tenant_id` passa a existir formalmente
- clínica vira uma representação legada ou subentidade operacional do tenant

---

## 5. Regras da transição

### Regra 1

Nenhum domínio transacional existente será migrado integralmente nesta etapa.

### Regra 2

Toda clínica atual deve ganhar um tenant correspondente do tipo `clinic`.

### Regra 3

O código deve aceitar os dois contextos durante a transição:

- `clinic_id` como compatibilidade operacional
- `tenant_id` como nova identidade estrutural

### Regra 4

Permissões continuam válidas mesmo antes da migração completa para `user_tenant_roles`.

### Regra 5

Novos domínios estruturais devem preferir `tenant_id`.

---

## 6. O que entra na fase atual

A fase atual cobre:

- criação de `tenant_types`
- criação de `tenants`
- criação de `tenant_branding`
- criação de `tenant_integrations`
- criação de `user_tenant_roles`
- inclusão de `tenant_id` em `clinics`
- seed dos tenants legados a partir das clínicas atuais
- seed de `user_tenant_roles` a partir de `user_clinics`
- exposição de `g.tenant_id`, `g.tenant_role` e `g.tenant_type` na request

---

## 7. O que fica para as próximas fases

- migração das tabelas clínicas para `tenant_id`
- substituição progressiva de consultas por tenant
- formalização de seleção de tenant na sessão
- RBAC completo baseado em `user_tenant_roles`
- tenants dos tipos `association` e `doctor` em operação real

---

## 8. Estratégia de compatibilidade no código

Durante a transição:

- `g.clinic_id` continua obrigatório para fluxos legados
- `g.tenant_id` passa a ser preenchido quando a estrutura nova estiver disponível
- `g.tenant_role` inicialmente espelha o vínculo atual por clínica
- `role_required` passa a aceitar o papel global e o papel contextual normalizado

---

## 9. Estratégia de rollout

### Passo 1

Aplicar a migration `004_tenants_foundation.sql`.

### Passo 2

Garantir que toda clínica atual esteja vinculada a um tenant.

### Passo 3

Ler `tenant_id` no contexto da request sem remover `clinic_id`.

### Passo 4

Criar novos domínios já orientados a `tenant_id`.

### Passo 5

Migrar domínios legados em ondas, e não em um corte único.

---

## 10. Critérios de sucesso desta etapa

- toda clínica existente possui tenant correspondente
- o código consegue expor `tenant_id` na request
- o sistema continua compatível com rotas e repositórios legados
- a próxima sprint pode começar jornadas e novos domínios já pensando em `tenant_id`

---

## 11. Riscos principais

| Risco | Mitigação |
|------|-----------|
| Quebra de queries legadas | manter `clinic_id` ativo |
| Ambiguidade de papéis | normalizar acesso via contexto |
| Migração incompleta de dados | seed idempotente a partir das clínicas atuais |
| Adoção prematura de `tenant_id` em todo o sistema | limitar esta fase à fundação |

---

## 12. Conclusão

A migração de `clinic_id` para `tenant_id` deve ser tratada como uma transição estrutural controlada.

O objetivo desta etapa não é concluir a migração, mas tornar a CannabIA capaz de evoluir para o modelo aprovado sem ruptura técnica desnecessária.
