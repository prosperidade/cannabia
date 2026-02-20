# CannabIA (Flask)

Documentação revisada para refletir o estado **atual** do código neste repositório.

## Visão geral

CannabIA é uma aplicação Flask focada em:

- recebimento de eventos do WhatsApp via webhook;
- persistência de mensagens e agendamentos em MySQL;
- dashboards web para tempo real, histórico e agendamento;
- autenticação básica de acesso com Flask-Login.

A aplicação principal está em `src/app.py`.

---

## Estrutura de pastas (estado atual)

```text
src/
  app.py                     # app principal (Flask + LoginManager + blueprints)
  config.py                  # variáveis de ambiente
  database.py                # conexão MySQL

  services/                  # regras de negócio
    message_service.py
    appointment_service.py

  repositories/              # acesso a dados SQL
    message_repository.py
    appointment_repository.py

  integrations/              # integrações externas
    whatsapp.py
    email.py

  templates/                 # páginas HTML (Jinja)
  static/
    js/

  realtime_notifications.py  # blueprint de webhook + dashboard realtime
  scheduling_chain.py        # blueprint de agendamento
  historico_atendimento.py   # blueprint de histórico
  dashboard.py               # app separado para /dashboard

docs/
  DOCUMENTACAO_SISTEMA.md

migrations/
  001_initial_schema.sql
```

### Sobre os caminhos pedidos (`src/web/routes`, `src/ai`, `src/infra`)

No estado atual do repositório, **essas pastas não existem**. Também não existe `src/infra/security.py`.

---

## Rotas principais

### App principal (`python -m src.app`)

- `GET /` → página inicial (protegida por login)
- `GET|POST /login` → login
- `POST /logout` → logout
- `GET /webhook` e `POST /webhook` → webhook do WhatsApp
- `GET /scheduling` e `POST /scheduling` → agendamentos (protegida)
- `GET /historico` → histórico de mensagens (protegida)
- `GET /` do blueprint realtime → dashboard realtime (protegida)

> Observação importante: o blueprint `realtime_bp` também registra `/`, então há conflito de rota com o `index` da app principal. Na prática, a última rota registrada tende a prevalecer.

### App separado de dashboard

- `GET /dashboard` está em `src/dashboard.py` e sobe em app separado (porta 5001 quando executado diretamente).

### Rotas solicitadas mas não encontradas no código atual

- `/whoami` → não implementada
- `/ai-audit` → não implementada
- `/ai/test` → não implementada
- `/realtime/*` → não há prefixo `/realtime`; o dashboard realtime está em `/`
- `/scheduling/*` → rota disponível é `/scheduling`
- `/historico/*` → rota disponível é `/historico`

---

## Autenticação e autorização (estado atual)

### O que existe hoje

- Flask-Login com `LoginManager` em `src/app.py`.
- `@login_required` aplicado em:
  - `/` (index)
  - dashboard realtime (`realtime_bp.route('/')`)
  - `/scheduling`
  - `/historico`
- Usuário de autenticação em memória (`AppUser`) com ID fixo (`default-user`).
- Credenciais vindas de variáveis de ambiente:
  - `APP_AUTH_USERNAME`
  - `APP_AUTH_PASSWORD`

### O que **não** existe hoje

- tabela `users` no banco para login;
- hash de senha com `bcrypt`;
- controle de perfis/roles (`Admin`, `Medico`, `Atendente`);
- decorator `@role_required`;
- módulo `src/infra/security.py`.

---

## Auditoria de IA (estado atual)

Não há, no código atual:

- tabela `ai_audit_logs`;
- campos como `total_tokens`, `estimated_cost_usd`;
- registro de status `success`, `validation_error`, `security_blocked`, `error` para trilha de auditoria de IA.

Os módulos de IA (`*_chain.py`) existem, mas não há camada de auditoria persistida para esses eventos neste repositório.

---

## Setup local (checklist)

## 1) Pré-requisitos

- Python 3.10+
- MySQL acessível

## 2) Criar e ativar ambiente virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

## 3) Instalar dependências

```bash
pip install -r requirements.txt
```

Se faltar pacote de autenticação:

```bash
pip install -r requirements-auth.txt
```

## 4) Criar `.env`

Exemplo mínimo:

```env
SECRET_KEY=sua_chave_forte
APP_AUTH_USERNAME=admin
APP_AUTH_PASSWORD=troque_esta_senha

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=cannabia

VERIFY_TOKEN=SEU_VERIFY_TOKEN
OPENAI_API_KEY=se_usar_modulos_llm
```

## 5) (Opcional) Aplicar migração inicial

```bash
python src/run_migrations.py
```

## 6) Subir aplicação

```bash
python -m src.app
```

---

## Diagrama textual de fluxo

```text
Request HTTP/Webhook
  -> (Flask Route/Blueprint)
  -> (Auth: Flask-Login / @login_required quando aplicável)
  -> Service (src/services/*)
  -> Repository (src/repositories/*)
  -> DB MySQL
```

---

## Troubleshooting

### 1) `ModuleNotFoundError: No module named 'flask'`

Instale as dependências no venv ativo:

```bash
pip install -r requirements.txt
```

### 2) Erros com `SECRET_KEY`

Defina `SECRET_KEY` no `.env` para não depender do valor padrão inseguro.

### 3) `OPENAI_API_KEY` ausente

Necessária apenas para módulos de IA (`anamnesis_chain.py`, `medical_history_chain.py`, `treatment_plans_chain.py`).

### 4) Erros de import ao rodar como módulo

O comando recomendado é:

```bash
python -m src.app
```

Se aparecer erro de import interno (por exemplo `from config import ...`), ajuste o ambiente para resolver o pacote `src` corretamente (ex.: executar a partir da raiz do projeto com venv ativo e dependências instaladas).

### 5) Problemas de conexão com MySQL

Revise variáveis `DB_*` no `.env` e valide acesso ao banco antes de subir a app.
