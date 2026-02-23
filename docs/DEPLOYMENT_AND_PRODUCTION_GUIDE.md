# DEPLOYMENT AND PRODUCTION GUIDE — CannabIA

> **Plataforma de Hospedagem:** [Render](https://render.com)
> **Runtime:** Python 3.x
> **Banco de Dados:** PostgreSQL (Render managed)
> **Servidor de Aplicação:** Gunicorn + Eventlet

---

## Arquitetura de Produção

```
Internet
    │
    ▼
┌─────────────────────────────┐
│    Render Web Service       │  (cannabia-api)
│  Gunicorn --worker eventlet │
│       src.app:app           │
└────────────┬────────────────┘
             │  DATABASE_URL (internal)
             ▼
┌─────────────────────────────┐
│   Render PostgreSQL         │  (cannabia-db)
│   Região: ohio (us-east-1)  │
└─────────────────────────────┘
```

---

## Pré-requisitos

1. Conta no [Render](https://render.com)
2. Repositório conectado ao Render (GitHub/GitLab)
3. Arquivo `render.yaml` na raiz do projeto (Infrastructure as Code)

---

## Passo a Passo do Deploy

### 1. Criar o Banco de Dados PostgreSQL

No painel do Render, crie um **PostgreSQL** service chamado `cannabia-db`.

- **Region:** `Ohio (us-east-1)` — menor latência para o Brasil
- **Plan:** `Starter` (gratuito para desenvolvimento)
- Anote a **Internal Database URL** — será usada pelo Web Service

### 2. Criar o Web Service

No painel do Render, crie um **Web Service** usando o repositório conectado.

- **Name:** `cannabia-api`
- **Runtime:** `Python`
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```bash
  gunicorn --worker-class eventlet --workers 1 --timeout 120 --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - "src.app:app"
  ```
- **Health Check Path:** `/whoami`

> **Por que 1 worker com eventlet?**
> O SocketIO (usado para notificações em tempo real) requer que todos os workers compartilhem o mesmo estado. Com `eventlet`, um único worker suporta múltiplas conexões simultâneas via I/O assíncrono.

---

## Variáveis de Ambiente

Configure as seguintes variáveis no painel do Render (**Environment > Environment Variables**):

### 🔌 Banco de Dados

| Variável       | Origem                                      | Descrição                   |
|----------------|---------------------------------------------|-----------------------------|
| `DATABASE_URL` | `fromDatabase: cannabia-db → connectionString` | URL de conexão PostgreSQL |

> O Render injeta automaticamente `DATABASE_URL` quando o Web Service e o Banco de Dados estão vinculados via `render.yaml`. O formato é:
> ```
> postgresql://USER:PASSWORD@HOST:PORT/DATABASE
> ```

O `src/config.py` lê essa variável diretamente:
```python
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("A variável de ambiente DATABASE_URL não foi definida.")
```

### 🤖 Inteligência Artificial

| Variável        | Valor          | Descrição                            |
|-----------------|----------------|--------------------------------------|
| `GOOGLE_API_KEY` | `<sua_chave>` | Chave da API do Google (Gemini/etc.) |
| `OPENAI_API_KEY` | `<sua_chave>` | Chave da API da OpenAI (GPT-4o-mini) |

### 📱 WhatsApp / Meta

| Variável                 | Descrição                                       |
|--------------------------|-------------------------------------------------|
| `META_WHATSAPP_KEY`      | Token de acesso à API do WhatsApp Business      |
| `WHATSAPP_PHONE_NUMBER_ID` | ID do número de telefone no Meta              |
| `WHATSAPP_APP_SECRET`    | Secret do App Meta para validação de webhooks   |
| `RECIPIENT_PHONE`        | Número de telefone padrão para envio            |
| `VERIFY_TOKEN`           | Token de verificação do webhook do Meta         |

### 🔒 Segurança

| Variável                | Valor                | Descrição                                     |
|-------------------------|----------------------|-----------------------------------------------|
| `SECRET_KEY`            | `generateValue: true` | Render gera automaticamente uma chave segura |
| `SESSION_COOKIE_SECURE` | `"true"`             | Obrigatório em HTTPS (produção)               |
| `SESSION_COOKIE_SAMESITE` | `"Lax"`            | Proteção CSRF                                 |

### 📧 Email

| Variável         | Descrição                              |
|------------------|----------------------------------------|
| `DOCTOR_EMAIL`   | Email do médico para notificações      |
| `EMAIL_FROM`     | Remetente dos emails do sistema        |
| `EMAIL_PASSWORD` | Senha do email (App Password do Gmail) |

### ⚡ Rate Limiting

| Variável               | Padrão | Descrição                             |
|------------------------|--------|---------------------------------------|
| `WEBHOOK_RATE_LIMIT`   | `60`   | Máx. requisições por janela           |
| `WEBHOOK_RATE_WINDOW_S`| `60`   | Janela de tempo em segundos           |
| `LOGIN_RATE_LIMIT`     | `10`   | Tentativas de login por janela        |
| `LOGIN_RATE_WINDOW_S`  | `60`   | Janela de tempo do login              |
| `MAX_CONTENT_LENGTH`   | `262144` | Tamanho máximo de payload (256KB)   |

---

## Migrations — Execução Automática

As migrations de banco de dados devem ser executadas **antes** da aplicação inicializar.

### Estratégia Atual

O arquivo `migrations/001_initial_schema.sql` contém toda a estrutura inicial do banco. Ele deve ser executado uma única vez no primeiro deploy.

### Como rodar as migrations no Render

Adicione a execução da migration ao **Build Command**:

```bash
pip install -r requirements.txt && python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
with open('migrations/001_initial_schema.sql', 'r') as f:
    cur.execute(f.read())
conn.commit()
cur.close()
conn.close()
print('Migration executada com sucesso.')
"
```

> **Por que no Build Command e não no Start Command?**
> O `buildCommand` é executado uma vez por deploy, antes da aplicação iniciar. O `startCommand` pode ser executado múltiplas vezes (re-deploys, restarts). O uso de `IF NOT EXISTS` e `ON CONFLICT DO NOTHING` no SQL garante idempotência — é seguro rodar o script múltiplas vezes.

---

## Deploy via `render.yaml` (Infrastructure as Code)

O arquivo `render.yaml` na raiz do projeto define toda a infraestrutura:

```yaml
services:
  - type: web
    name: cannabia-api
    runtime: python
    region: ohio
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: >
      gunicorn
      --worker-class eventlet
      --workers 1
      --timeout 120
      --bind 0.0.0.0:$PORT
      "src.app:app"
    healthCheckPath: /whoami
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: cannabia-db
          property: connectionString
```

---

## Verificação Pós-Deploy

Após o deploy, verifique se o serviço está funcionando:

```bash
# Health check
curl https://<sua-app>.onrender.com/whoami

# Resposta esperada:
# {"authenticated": false, "user_id": null, "role": null}
```

Se o status code for `200`, a aplicação está online e conectada ao banco.

---

## Troubleshooting

| Problema                                   | Causa Provável                                   | Solução                                             |
|--------------------------------------------|--------------------------------------------------|-----------------------------------------------------|
| `RuntimeError: DATABASE_URL não definida`  | Variável não configurada no Render               | Vincule o Web Service ao banco via `fromDatabase`   |
| `psycopg2.OperationalError: Connection refused` | URL incorreta ou banco parado               | Verifique se o serviço PostgreSQL está ativo        |
| `ModuleNotFoundError`                      | Dependência não instalada                        | Verifique `requirements.txt`                        |
| Login retorna 401 mesmo com senha correta  | Hash no seed SQL é inválido                      | Rode `create_admin.py` para gerar um hash real      |
| SocketIO não conecta                       | Workers > 1 sem sticky sessions                  | Mantenha `--workers 1` com `eventlet`               |
