# TECHNICAL CONTEXT - CannabIA

Este documento detalha a arquitetura, as integrações e a stack de tecnologias em uso no **CannabIA**, fornecendo a clareza técnica necessária para desenvolvedores (ou IAs auxiliares) trabalharem no projeto.

## Estrutura de Pastas e Módulos Principais
A base de código (`src/`) segue um padrão modular baseado nas responsabilidades, usando Flask (Blueprints):

```
src/
├── ai/                      # Lógica principal do agente e modelos de linguagem
│   ├── chains.py            # Interfaces com as APIs OpenAI (gpt-4o-mini) e Google (Gemini 1.5)
│   ├── pipeline.py          # O orquestrador das 3 etapas clínicas: Anamnese -> Tratamento -> Relatório Científico
│   ├── prompts.py           # Definições estritas (JSON) de Engenharia de Prompt (Análise, Plano, Relatório RAG)
│   ├── schemas.py           # Schemas Pydantic garantindo o formato da entrada e saída da IA
│   ├── service.py           # Camada de serviço, lida com criação de paciente e auditorias/erros
│   └── validators.py        # Proteções anti-prompt injection
│
├── infra/                   # Camada de banco de dados e utilitários base
│   └── database.py          # Context manager do psycopg2 (db_cursor)
│
├── integrations/            # Serviços de terceiros
│   └── whatsapp.py          # Envio ativo de templates/mensagens da Meta (requests HTTP)
│
├── knowledge/               # Sistema RAG (Retrieval-Augmented Generation)
│   ├── embeddings.py        # Cliente de vetorização
│   └── vector_store.py      # Operações no ChromaDB local (`chroma_db/` - persiste embeddings em disco)
│
├── repositories/            # Camada de acesso direto ao PostgreSQL (CRUD)
│   ├── ai_audit_repository.py
│   ├── patient_repository.py
│   └── user_repository.py
│
├── web/                     # Rotas HTTP e Webhooks (Flask Blueprints e Socket.IO)
│   └── routes/
│       ├── auth.py          # Segurança (CSRF, Rate Limiting de login)
│       └── realtime_notifications.py  # Handler de eventos do Webhook Meta / WhatsApp
│
└── app.py                   # App Factory Flask (inicia blueprints, login_manager, multi-tenant middleware)
```

## Stack Tecnológico Real
1. **Framework Web:** Python 3.12, Flask 3.x, Flask-SocketIO. O servidor de produção roda com `Gunicorn + Eventlet` (para suporte assíncrono real-time).
2. **Persistência Relacional:** PostgreSQL (Render Managed) com `psycopg2`. Utiliza colunas `JSONB` na tabela de auditoria para flexibilidade de logs das IAs.
3. **Módulo de IA (Modelos Múltiplos):**
   - Etapa 1 e 2 (Análise Clínica e Plano): OpenAI API (`gpt-4o-mini`). Exige temperatura 0 e JSON estruturado (Pydantic).
   - Etapa 3 (Relatório RAG): Google GenAI (`gemini-1.5-flash`), usado pelo seu grande limite de contexto em junção com a busca vetorial.
4. **Base de Conhecimento RAG:**
   - Vetorização usando APIs de Embedding do Google.
   - Armazenamento em **ChromaDB** (`chromadb.PersistentClient`).
   - Leitura de artigos médicos por `PyMuPDF` (presente em `requirements.txt`).
5. **Comunicação Ativa:** API Oficial do WhatsApp Business (Meta). A biblioteca `requests` consome a API do Graph Facebook (v22.0) com tokens de acesso bearer.

## Entendendo o Pipeline RAG (Retrieval-Augmented Generation)
A Etapa 2.5 (`src/ai/pipeline.py`) cruza os dados dos sintomas e o plano terapêutico inicial (gerado pelo GPT-4o-mini) com o `KnowledgeStore`:

1. Uma query JSON (ex: `{"cannabinoid_ratio": "1:1", "precautions": [...]}`) é convertida em um vetor (embedding).
2. O ChromaDB retorna os 5 "chunks" (trechos de artigos científicos em `chroma_db`) mais similares usando *cosine similarity*.
3. Estes textos e DOIs (metadata) são formatados e injetados no prompt estruturado do Google Gemini (prompt `SCIENTIFIC_REPORT_RAG_PROMPT`), que elabora um documento de evidências, justificando clinicamente as decisões sugeridas na Etapa 2.
4. *Fallback Silencioso*: Caso o ChromaDB esteja vazio ou falhe, o sistema chama automaticamente o `gpt-4o-mini` para uma versão de relatório sem evidências externas diretas.

## O Webhook da Meta: Segurança e Processamento (`realtime_notifications.py`)
A integração do WhatsApp usa duas requisições na mesma rota `/webhook/meta`:
- **GET**: É disparado apenas pela Meta para registrar o URL do webhook. Compara o token enviado com a variável `VERIFY_TOKEN`.
- **POST**: É a mensagem real enviada pelo paciente, ou atualizações de "lida/entregue".

A segurança vital do projeto obriga o backend a computar e comparar um HMAC-SHA256 entre o **raw payload recebido e o `WHATSAPP_APP_SECRET`** para barrar requisições falsas que imitem a Meta:

```python
def _verify_hmac_meta(raw_body: bytes) -> bool:
    '''Valida X-Hub-Signature-256 enviada pela Meta no header da request.'''
    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False

    expected = header[len("sha256="):]
    computed = hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected)
```
*Trecho retirado de `src/web/routes/realtime_notifications.py`.*