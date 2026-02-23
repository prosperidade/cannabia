# CannabIA 🌿

**Plataforma de Inteligência Artificial para Cannabis Medicinal**

Uma aplicação web multi-tenant desenvolvida em Python/Flask, integrada com modelos de LLM (OpenAI GPT-4o-mini e Google Gemini), banco de dados relacional PostgreSQL, e a API de WhatsApp Business da Meta.

---

## 🎯 O que é o CannabIA?

O CannabIA é um sistema clínico que auxilia médicos no tratamento com Cannabis Medicinal. A plataforma processa dados de anamnese do paciente e retorna, em segundos, uma análise clínica estruturada, um plano terapêutico personalizado com dosagem e via de administração, e um relatório científico embasado em literatura médica.

O sistema foi projetado para funcionar em múltiplas clínicas simultaneamente (multi-tenancy), com isolamento total de dados entre elas.

---

## 🏗️ Stack Tecnológica

| Camada              | Tecnologia                                        |
|---------------------|---------------------------------------------------|
| **Backend**         | Python 3.12 · Flask 3.x · Flask-Login · SocketIO  |
| **Servidor**        | Gunicorn + Eventlet                               |
| **Banco de Dados**  | PostgreSQL (Render managed) · psycopg2            |
| **IA — Análise**    | OpenAI GPT-4o-mini                                |
| **IA — Relatório**  | Google Gemini 1.5 Flash                           |
| **Busca Semântica** | ChromaDB · Google text-embedding-004 (RAG)        |
| **Mensageria**      | Meta/WhatsApp Business API (webhooks)             |
| **Validação**       | Pydantic v2                                       |
| **Hospedagem**      | Render (Ohio/us-east-1)                           |
| **Email**           | SMTP/Gmail                                        |

---

## 🚀 Quick Start — Desenvolvimento Local

### Pré-requisitos

- Python 3.12+
- PostgreSQL rodando localmente (ou uma instância no Render)
- Chaves de API: OpenAI e Google

### 1. Clonar e configurar

```bash
git clone <repo-url>
cd cannabia
python -m venv env
env\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 2. Configurar variáveis de ambiente

Copie o `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

**Variáveis obrigatórias:**

```env
# Banco de Dados (PostgreSQL)
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE

# Inteligência Artificial
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# Segurança
SECRET_KEY=uma-chave-secreta-aleatoria-longa
```

> **⚠️ Nunca commite o arquivo `.env` no repositório.** Ele já está no `.gitignore`.

### 3. Executar migrations

```bash
python -c "
import os, psycopg2
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
with open('migrations/001_initial_schema.sql', 'r') as f:
    cur.execute(f.read())
conn.commit()
print('Migration executada.')
"
```

### 4. Criar usuário administrador

```bash
python create_admin.py
```

### 5. Iniciar a aplicação

```bash
python -m flask --app src.app run --debug
```

A aplicação estará disponível em `http://localhost:5000`.

---

## 🏢 Multi-Tenancy

O CannabIA suporta múltiplas clínicas. Cada clínica possui:
- Dados de pacientes completamente isolados
- Usuários com roles específicos por clínica (`clinic_admin`, `medico`)
- Possibilidade de um médico pertencer a múltiplas clínicas

O isolamento é garantido pela coluna `clinic_id` em todas as tabelas de dados clínicos e validado a cada requisição via `src/tenancy.py`.

---

## 🤖 Pipeline de IA

Cada caso clínico passa por 3 etapas:

```
Anamnese do Paciente
       │
       ▼
[Etapa 1] Análise Clínica        → GPT-4o-mini
       │
       ▼
[Etapa 2] Plano Terapêutico      → GPT-4o-mini
       │
       ▼
[Etapa 2.5] Busca Semântica (RAG) → ChromaDB + text-embedding-004
       │
       ▼
[Etapa 3] Relatório Científico   → Gemini 1.5 Flash (ou GPT-4o-mini fallback)
       │
       ▼
[Auditoria] PostgreSQL ai_audit_logs (tokens, custo, payload completo)
```

---

## 📱 Integração WhatsApp

O sistema recebe mensagens de pacientes via webhook da API do WhatsApp Business (Meta). As mensagens são armazenadas na tabela `incoming_messages` e processadas de forma assíncrona.

**Configuração necessária:**
- Criar um App no [Meta for Developers](https://developers.facebook.com)
- Configurar o webhook apontando para `https://<sua-app>.onrender.com/webhook`
- Definir as variáveis `META_WHATSAPP_KEY`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `VERIFY_TOKEN`

---

## 🚢 Deploy em Produção

O deploy é feito no **Render** via `render.yaml` (Infrastructure as Code).

```bash
# O Render detecta o render.yaml automaticamente ao conectar o repositório.
# Basta configurar as variáveis de ambiente no painel e fazer push.
```

Consulte o [DEPLOYMENT_AND_PRODUCTION_GUIDE.md](docs/DEPLOYMENT_AND_PRODUCTION_GUIDE.md) para instruções detalhadas.

---

## 📂 Estrutura do Projeto

```
cannabia/
├── src/
│   ├── app.py                    # Factory da aplicação Flask
│   ├── config.py                 # Configurações via variáveis de ambiente
│   ├── tenancy.py                # Hook de resolução de clínica por request
│   ├── ai/
│   │   ├── service.py            # Orquestrador do pipeline de IA
│   │   ├── pipeline.py           # As 3 etapas do pipeline clínico
│   │   ├── chains.py             # Chamadas individuais aos LLMs
│   │   ├── schemas.py            # Schemas Pydantic de entrada/saída
│   │   ├── validators.py         # Anti prompt injection
│   │   └── pricing.py            # Cálculo de custo por tokens
│   ├── repositories/
│   │   ├── user_repository.py    # CRUD de usuários
│   │   ├── patient_repository.py # CRUD de pacientes (com clinic_id)
│   │   ├── ai_audit_repository.py# Persistência dos logs de IA
│   │   └── tenancy_repository.py # Resolução de clínica padrão
│   ├── infra/
│   │   └── database.py           # Context manager db_cursor (psycopg2)
│   └── web/
│       └── routes/               # Blueprints Flask
├── migrations/
│   └── 001_initial_schema.sql    # Schema completo PostgreSQL
├── docs/
│   ├── DATABASE_SCHEMA.md
│   ├── DEPLOYMENT_AND_PRODUCTION_GUIDE.md
│   ├── AI_MODULE_DOCUMENTATION.md
│   └── AUTHORIZATION_AND_MULTI_TENANCY.md
├── render.yaml                   # Infrastructure as Code (Render)
├── requirements.txt
└── .env.example
```

---

## 📚 Documentação Técnica

| Documento | Descrição |
|-----------|-----------|
| [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) | Estrutura completa do banco PostgreSQL |
| [DEPLOYMENT_AND_PRODUCTION_GUIDE.md](docs/DEPLOYMENT_AND_PRODUCTION_GUIDE.md) | Deploy no Render, variáveis de ambiente, migrations |
| [AI_MODULE_DOCUMENTATION.md](docs/AI_MODULE_DOCUMENTATION.md) | Pipeline de IA, RAG, auditoria e custos |
| [AUTHORIZATION_AND_MULTI_TENANCY.md](docs/AUTHORIZATION_AND_MULTI_TENANCY.md) | Isolamento por clínica, Flask-Login, Regra de Ouro |

---

## 🔒 Segurança

- **Senhas:** Armazenadas com hash bcrypt
- **Sessões:** Cookies seguros (HTTPS only em produção)
- **CSRF:** Todos os formulários protegidos com tokens de sessão
- **Rate Limiting:** Limite de tentativas de login
- **Multi-tenancy:** Dados de pacientes isolados por `clinic_id`
- **Anti Injection:** Validação contra prompt injection antes de cada chamada de IA

---

## 📋 Credenciais Padrão (Ambiente de Desenvolvimento)

> **Nunca use estas credenciais em produção.**

Após rodar a migration e o `create_admin.py`, acesse com:

- **Usuário:** `admin`
- **Senha:** definida ao rodar `create_admin.py`

---

## 🤝 Contribuindo

1. Faça um fork do repositório
2. Crie uma branch: `git checkout -b feature/nome-da-feature`
3. Commit suas mudanças: `git commit -m 'feat: descrição'`
4. Push para a branch: `git push origin feature/nome-da-feature`
5. Abra um Pull Request

---

*CannabIA — Tecnologia a serviço da saúde integrativa.*
