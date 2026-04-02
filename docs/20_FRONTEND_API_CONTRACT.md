# 20 — Frontend API Contract

## 1. Objetivo

Definir o contrato inicial de API entre:

- **backend Flask**
- **frontend Next.js**

Este documento descreve:

- os endpoints prioritários
- o formato de request/response
- regras de autenticação
- contexto de tenant/clinic
- ordem de implementação

Este é um **contrato-alvo** para a próxima fase. Hoje o sistema ainda é majoritariamente server-rendered em Jinja.

---

## 2. Premissas

### 2.1. Backend continua sendo a fonte de verdade

O frontend não carrega regra de negócio clínica sensível.

O backend continua responsável por:

- autenticação
- autorização
- contexto de tenant/clinic
- validação de domínio
- persistência
- auditoria
- integrações

### 2.2. Convenções técnicas do contrato

- prefixo padrão: `/api/v1`
- payloads em `application/json`
- datas em ISO 8601
- IDs numéricos enquanto a base atual permanecer assim
- autenticação inicial por **cookie de sessão**
- requests autenticadas do frontend devem usar `credentials: "include"`

### 2.3. Estratégia de transição

No início:

- o frontend legado continuará chamando rotas HTML
- o Next.js consumirá os novos endpoints JSON
- backend serve os dois modelos em paralelo

---

## 3. Convenção de resposta

## 3.1. Resposta de sucesso

```json
{
  "data": {},
  "meta": {}
}
```

`meta` é opcional.

## 3.2. Resposta de erro

```json
{
  "error": {
    "code": "validation_error",
    "message": "appointment_date é obrigatório.",
    "details": {}
  }
}
```

## 3.3. Códigos HTTP esperados

- `200` leitura bem-sucedida
- `201` criação bem-sucedida
- `400` payload inválido
- `401` usuário não autenticado
- `403` usuário sem permissão
- `404` recurso inexistente
- `409` conflito de estado
- `422` erro semântico de validação
- `500` erro interno

---

## 4. Autenticação e sessão

## 4.1. Decisão inicial

O contrato inicial usará **sessão baseada em cookie**, aproveitando a autenticação atual do Flask.

Isso evita criar agora:

- JWT
- refresh token
- auth service separado
- dupla infraestrutura de login

## 4.2. CSRF

Enquanto a autenticação continuar por cookie de sessão:

- requests `POST`, `PUT`, `PATCH` e `DELETE` devem enviar token CSRF
- o backend deve expor o token em endpoint próprio ou na resposta de sessão

## 4.3. Endpoints de sessão prioritários

### `GET /api/v1/session/me`

Retorna contexto do usuário autenticado.

```json
{
  "data": {
    "authenticated": true,
    "user": {
      "id": 1,
      "username": "admin",
      "role": "Admin",
      "global_role": "Admin"
    },
    "context": {
      "clinic_id": 1,
      "clinic_role": "clinic_admin",
      "tenant_id": 1,
      "tenant_role": "tenant_admin",
      "tenant_type": "clinic"
    },
    "csrf_token": "token"
  }
}
```

### `POST /api/v1/session/login`

Request:

```json
{
  "username": "admin",
  "password": "senha"
}
```

Response:

```json
{
  "data": {
    "authenticated": true,
    "user": {
      "id": 1,
      "username": "admin",
      "role": "Admin"
    },
    "context": {
      "clinic_id": 1,
      "tenant_id": 1
    },
    "csrf_token": "token"
  }
}
```

### `POST /api/v1/session/logout`

Response:

```json
{
  "data": {
    "success": true
  }
}
```

---

## 5. Contexto de tenant e clinic

## 5.1. Regra inicial

No estado atual, o backend resolve o escopo principal por `clinic_id` e está em transição para `tenant_id`.

Para o frontend novo:

- `clinic_id` ainda será tratado como contexto obrigatório
- `tenant_id` já deve ser retornado sempre que disponível

## 5.2. Regra de consumo

O frontend não deve inferir escopo sozinho.

Ele deve consumir o contexto retornado por:

- `GET /api/v1/session/me`

## 5.3. Evolução futura

Quando a seleção de tenant ativo ficar mais madura, podemos introduzir:

- `X-Active-Tenant-Id`
- `X-Active-Clinic-Id`

No estado atual, isso ainda não é obrigatório.

---

## 6. Endpoints prioritários para a Fase 1 do Next.js

## 6.1. Dashboard

### `GET /api/v1/dashboard`

Finalidade:

- KPIs principais
- agregações por contato
- agregações por dia

Response:

```json
{
  "data": {
    "metrics": {
      "total_messages": 120,
      "total_patients": 40,
      "total_appointments": 12,
      "total_ai": 18
    },
    "charts": {
      "messages_by_contact": [
        { "label": "Maria", "count": 18 }
      ],
      "messages_by_day": [
        { "date": "2026-04-01", "count": 42 }
      ]
    }
  }
}
```

### `GET /api/v1/dashboard/messages`

Query params:

- `sender`
- `page`
- `page_size`

Response:

```json
{
  "data": [
    {
      "id": 1,
      "sender": "5511999999999",
      "contact_name": "Maria",
      "message_text": "Oi",
      "timestamp": "2026-04-01T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20
  }
}
```

---

## 6.2. Atendimentos

### `GET /api/v1/attendances`

Query params:

- `status`
- `page`
- `page_size`

Response:

```json
{
  "data": [
    {
      "id": 10,
      "patient_id": 5,
      "patient_name": "João Silva",
      "phone": "5511999999999",
      "status": "pendente",
      "report_model": "gpt-4o-mini",
      "rag_chunks_used": 4,
      "created_at": "2026-04-01T13:10:00Z"
    }
  ],
  "meta": {
    "total": 1,
    "page": 1,
    "page_size": 20
  }
}
```

### `GET /api/v1/attendances/{report_id}`

Response:

```json
{
  "data": {
    "report": {
      "id": 10,
      "patient_id": 5,
      "patient_name": "João Silva",
      "phone": "5511999999999",
      "status": "pendente",
      "anamnesis_data": {},
      "clinical_analysis": {},
      "treatment_plan": {},
      "scientific_report": {},
      "created_at": "2026-04-01T13:10:00Z"
    },
    "timeline": [],
    "medical_record_entries": [],
    "consultation_entry": null
  }
}
```

### `POST /api/v1/attendances/{report_id}/review`

Request:

```json
{}
```

Response:

```json
{
  "data": {
    "reviewed": true,
    "report_id": 10,
    "status": "revisado"
  }
}
```

### `POST /api/v1/attendances/{report_id}/medical-record`

Request:

```json
{
  "consultation_status": "consulta_realizada",
  "medical_observations": "Paciente compareceu bem orientado.",
  "clinical_assessment": "Quadro compatível com dor crônica e ansiedade associada.",
  "conduct": "Manter ajuste inicial e retorno em 30 dias.",
  "requested_exams": ["hemograma", "função hepática"],
  "follow_up_plan": "Monitoramento semanal por 4 semanas."
}
```

Response:

```json
{
  "data": {
    "saved": true,
    "medical_record_id": 3,
    "entry_id": 7,
    "created": true
  }
}
```

---

## 6.3. Timeline do paciente

### `GET /api/v1/patients/{patient_id}/timeline`

Response:

```json
{
  "data": [
    {
      "id": 1,
      "event_type": "anamnesis_completed",
      "journey_stage": "anamnese_concluida",
      "title": "Anamnese assistida concluída",
      "description": "Fluxo do WhatsApp finalizado com relatório clínico gerado pela IA.",
      "source_type": "anamnesis_report",
      "source_id": 10,
      "event_time": "2026-04-01T13:10:00Z",
      "metadata": {
        "report_model": "gpt-4o-mini",
        "risk_level": "médio"
      }
    }
  ]
}
```

---

## 6.4. Prontuário longitudinal

### `GET /api/v1/patients/{patient_id}/medical-record`

Response:

```json
{
  "data": {
    "medical_record": {
      "id": 3,
      "patient_id": 5,
      "status": "ativo",
      "opened_at": "2026-04-01T13:10:00Z",
      "last_entry_at": "2026-04-01T14:00:00Z"
    },
    "entries": [
      {
        "id": 7,
        "entry_type": "consultation_note",
        "title": "Registro clínico da consulta",
        "status": "consulta_realizada",
        "author_name": "admin",
        "medical_observations": "Paciente evoluindo bem.",
        "clinical_assessment": "Melhora parcial.",
        "conduct": "Manter plano.",
        "requested_exams": ["hemograma"],
        "follow_up_plan": "Retorno em 30 dias.",
        "created_at": "2026-04-01T14:00:00Z"
      }
    ]
  }
}
```

---

## 6.5. Agendamentos

### `GET /api/v1/appointments`

Response:

```json
{
  "data": [
    {
      "id": 2,
      "patient_id": 5,
      "patient_name": "João Silva",
      "appointment_date": "2026-04-23T14:30:00Z",
      "status": "Agendada",
      "created_at": "2026-04-01T14:05:00Z"
    }
  ]
}
```

### `POST /api/v1/appointments`

Request:

```json
{
  "patient_name": "João Silva",
  "appointment_date": "2026-04-23T14:30:00Z"
}
```

Response:

```json
{
  "data": {
    "created": true,
    "appointment_id": 2
  }
}
```

---

## 6.6. Histórico de mensagens

### `GET /api/v1/messages`

Query params:

- `sender`
- `page`
- `page_size`

Response:

```json
{
  "data": [
    {
      "id": 1,
      "sender": "5511999999999",
      "contact_name": "Maria",
      "message_text": "Oi",
      "timestamp": "2026-04-01T10:30:00Z"
    }
  ]
}
```

---

## 6.7. Auditoria de IA

### `GET /api/v1/admin/ai-metrics`

Response:

```json
{
  "data": {
    "summary": {
      "total_execucoes": 12,
      "total_tokens": 32000,
      "total_cost_usd": 1.42,
      "sucessos": 10,
      "erros": 1,
      "bloqueios": 1,
      "tempo_medio_ms": 945
    },
    "recent_logs": []
  }
}
```

---

## 7. Endpoints auxiliares recomendados

## 7.1. Diagnóstico de contexto

### `GET /api/v1/context`

Retorna:

- `clinic_id`
- `clinic_role`
- `tenant_id`
- `tenant_role`
- `tenant_type`

Pode ser unificado com `session/me`, mas vale manter a necessidade explícita no desenho.

## 7.2. Health frontend/backend

### `GET /api/v1/health`

Response:

```json
{
  "data": {
    "status": "ok"
  }
}
```

---

## 8. Mapeamento entre rotas atuais e APIs-alvo

| Atual | Tipo atual | API alvo |
|------|------------|----------|
| `/whoami` | JSON técnico | `/api/v1/session/me` |
| `/clinic-debug` | JSON técnico | `/api/v1/context` |
| `/dashboard` | HTML | `/api/v1/dashboard` + `/api/v1/dashboard/messages` |
| `/historico/historico` | HTML | `/api/v1/messages` |
| `/atendimentos` | HTML | `/api/v1/attendances` |
| `/atendimentos/<report_id>` | HTML | `/api/v1/attendances/{report_id}` |
| `/atendimentos/<report_id>/revisar` | POST form | `/api/v1/attendances/{report_id}/review` |
| `/atendimentos/<report_id>/prontuario` | POST form | `/api/v1/attendances/{report_id}/medical-record` |
| `/scheduling/scheduling` | HTML + POST form | `/api/v1/appointments` |
| `/admin/ai-metrics` | HTML | `/api/v1/admin/ai-metrics` |

---

## 9. Ordem de implementação recomendada

1. `GET /api/v1/session/me`
2. `POST /api/v1/session/login`
3. `POST /api/v1/session/logout`
4. `GET /api/v1/dashboard`
5. `GET /api/v1/attendances`
6. `GET /api/v1/attendances/{report_id}`
7. `POST /api/v1/attendances/{report_id}/review`
8. `POST /api/v1/attendances/{report_id}/medical-record`
9. `GET /api/v1/patients/{patient_id}/timeline`
10. `GET /api/v1/patients/{patient_id}/medical-record`
11. `GET /api/v1/appointments`
12. `POST /api/v1/appointments`

---

## 10. Regras de segurança para o contrato

- toda leitura sensível respeita `clinic_id` e, quando disponível, `tenant_id`
- nenhuma rota clínica pode ignorar autorização por papel
- respostas não devem vazar dados de outro tenant/clinic
- mutações com cookie de sessão devem exigir CSRF
- logs de erro não devem expor dados clínicos brutos ao frontend

---

## 11. Regras de frontend para consumo da API

- usar cliente HTTP único
- enviar `credentials: "include"`
- centralizar tratamento de `401` e `403`
- tratar `session/me` como fonte oficial de autenticação
- não inferir permissão apenas pela UI
- não decidir tenant/clinic por heurística de frontend

---

## 12. Próximo passo após este documento

Depois deste contrato, o próximo passo recomendado é:

1. criar os endpoints JSON da camada de sessão e contexto
2. subir o bootstrap do projeto `frontend/` em Next.js
3. implementar primeiro o fluxo:

```text
login -> shell autenticado -> atendimentos -> detalhe -> timeline -> prontuário
```
