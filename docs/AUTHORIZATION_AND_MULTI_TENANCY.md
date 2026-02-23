# AUTHORIZATION AND MULTI-TENANCY — CannabIA

> **Framework:** Flask-Login + `flask.g` context
> **Isolamento:** `clinic_id` em todas as tabelas tenantadas
> **Arquivo central:** `src/tenancy.py`

---

## Modelo de Multi-Tenancy

O CannabIA utiliza uma arquitetura **multi-tenant de banco compartilhado com discriminador de linha (`clinic_id`)**. Todas as clínicas residem no mesmo banco PostgreSQL, porém cada tabela sensível possui a coluna `clinic_id` como discriminador obrigatório.

```
┌──────────────────────────────────────────────────────┐
│                  PostgreSQL (único BD)               │
│                                                      │
│  ┌─────────────┐     ┌─────────────┐                │
│  │  Clínica A  │     │  Clínica B  │                │
│  │ clinic_id=1 │     │ clinic_id=2 │                │
│  └──────┬──────┘     └──────┬──────┘                │
│         │                   │                        │
│         ▼                   ▼                        │
│  patients WHERE        patients WHERE                │
│  clinic_id=1           clinic_id=2                  │
│  (isolado)             (isolado)                    │
└──────────────────────────────────────────────────────┘
```

---

## Autenticação — Flask-Login

A autenticação de usuários é gerenciada pelo **Flask-Login** via a classe `AppUser` definida em `src/app.py`.

### Classe `AppUser`

```python
class AppUser(UserMixin):
    def __init__(self, user_id: int, username: str, role: str):
        self.id       = str(user_id)   # Flask-Login exige string
        self.username = username
        self.role     = role
```

### Fluxo de Login

```
POST /login
     │
     ├─ [CSRF] Valida CSRF token do formulário
     ├─ get_user_by_username(username)
     │     └─ SELECT * FROM users WHERE username = %s AND is_active = TRUE
     ├─ verify_password(password, user["password_hash"])  ← bcrypt
     └─ login_user(AppUser(...))
               │
               ▼
         Flask-Login define session["_user_id"]
```

### `@login_required`

Qualquer rota decorada com `@login_required` aborta com redirect para `/login` se o usuário não estiver autenticado. **Nenhuma rota de acesso a dados de pacientes existe sem este decorator.**

---

## Resolução de Contexto de Clínica (Tenancy)

Após a autenticação, o módulo `src/tenancy.py` é ativado via `@app.before_request` em **toda requisição autenticada**.

### `attach_clinic_context()` — Fluxo Completo

```python
@app.before_request
def attach_clinic_context():
    # 1. Ignora rotas públicas (login, static)
    if request.path.startswith("/static") or request.path == "/login":
        return
    
    # 2. Ignora usuários não autenticados
    if not current_user.is_authenticated:
        return
    
    user_id = int(current_user.id)
    
    # 3. Tenta recuperar a clínica ativa da sessão
    clinic_id = session.get("active_clinic_id")
    
    # 4. Se não houver clínica na sessão, resolve a padrão
    if clinic_id is None:
        clinic_id = resolve_default_clinic_id(user_id)
        if clinic_id is None:
            abort(403)                           # Usuário sem clínica → 403
        session["active_clinic_id"] = clinic_id
    
    # 5. Verifica o vínculo ativo do usuário com a clínica
    membership = get_user_membership(user_id, clinic_id)
    if membership is None:
        abort(403)                               # Sem permissão → 403
    
    # 6. Anexa no contexto global da request
    g.clinic_id   = membership["clinic_id"]
    g.clinic_role = membership["role"]
```

### Resultado

Após este hook, **toda request autenticada** tem `flask.g.clinic_id` preenchido automaticamente, sem necessidade de passá-lo manualmente.

---

## A Tabela `user_clinics` — Coração do Multi-Tenancy

```sql
CREATE TABLE IF NOT EXISTS user_clinics (
    user_id    INT NOT NULL,
    clinic_id  INT NOT NULL,
    role       VARCHAR(50) NOT NULL,    -- 'clinic_admin', 'medico'
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, clinic_id)
);
```

| Conceito         | Explicação                                                   |
|------------------|--------------------------------------------------------------|
| PK composta      | Um usuário pode ser vinculado a N clínicas                   |
| `role`           | Papel específico dentro desta clínica                        |
| `is_default`     | Clínica carregada automaticamente no login                   |
| Verificação      | `get_user_membership(user_id, clinic_id)` valida o vínculo  |

---

## Resolução da Clínica Padrão

`resolve_default_clinic_id(user_id)` em `src/repositories/tenancy_repository.py`:

```python
# Tenta encontrar a clínica marcada como padrão
SELECT clinic_id FROM user_clinics WHERE user_id=%s AND is_default=TRUE LIMIT 1

# Se não houver padrão, pega a mais antiga
SELECT clinic_id FROM user_clinics WHERE user_id=%s ORDER BY created_at ASC LIMIT 1
```

---

## ⚠️ A Regra de Ouro — Isolamento de Dados

> **NUNCA faça SELECT em tabelas tenantadas sem filtrar por `clinic_id`.**

Esta é a regra mais crítica do sistema. Violá-la exporia dados de pacientes de uma clínica para outra, quebrando a privacidade e conformidade legal (LGPD).

### Padrão Correto

```python
# ✅ CORRETO — sempre filtrando pelo clinic_id da request atual
def get_patients(clinic_id: int):
    cursor.execute(
        "SELECT * FROM patients WHERE clinic_id = %s",
        (clinic_id,)
    )

# ❌ ERRADO — acessaria pacientes de TODAS as clínicas
def get_patients_WRONG():
    cursor.execute("SELECT * FROM patients")
```

### Como obter o `clinic_id` nos repositórios

O `clinic_id` é sempre obtido de `flask.g`, que é preenchido automaticamente pelo `tenancy.py`:

```python
from flask import g

clinic_id = g.clinic_id  # Sempre seguro nas rotas autenticadas
```

---

## CSRF Protection

Todas as operações de mutação (POST/formulários) são protegidas contra CSRF.

**Geração:** `generate_csrf_token()` — cria um token aleatório na sessão
**Validação:** `_validate_csrf_from_form_compat()` — usa `secrets.compare_digest()` para evitar timing attacks

```python
# Cada formulário de login/logout inclui:
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

---

## Rate Limiting

O endpoint `/login` possui rate limiting para prevenir ataques de força bruta:

| Configuração       | Variável de Ambiente  | Padrão |
|--------------------|-----------------------|--------|
| Máx. tentativas    | `LOGIN_RATE_LIMIT`    | `10`   |
| Janela de tempo    | `LOGIN_RATE_WINDOW_S` | `60s`  |

Se o limite for excedido, a função `limit_or_429()` retorna HTTP `429 Too Many Requests`.

---

## Resumo de Proteções

| Camada             | Mecanismo                                 | Arquivo                   |
|--------------------|-------------------------------------------|---------------------------|
| Autenticação       | Flask-Login + bcrypt                      | `src/app.py`              |
| Contexto de clínica| `before_request` + `flask.g`              | `src/tenancy.py`          |
| Acesso a dados     | Filtro obrigatório `WHERE clinic_id=%s`   | `src/repositories/*.py`   |
| CSRF               | Token de sessão + `secrets.compare_digest`| `src/web/routes/auth.py`  |
| Rate limiting      | Contadores em memória por IP/chave        | `src/web/routes/auth.py`  |
| Sessão segura      | `SESSION_COOKIE_SECURE=true` em produção  | `src/config.py`           |
