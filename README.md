# 🌿 Cannab'IA

Sistema clínico inteligente com integração WhatsApp, notificações em tempo real e pipeline estruturado de IA para análise médica baseada em cannabis medicinal.

---

## 🏗 Arquitetura

O projeto segue arquitetura modular em camadas utilizando padrão `src/`.
src/
│
├── app.py # Application Factory
├── config.py # Configurações (.env)
│
├── ai/ # Pipeline de IA estruturado
├── web/routes/ # Blueprints Flask (camada web)
├── services/ # Regras de negócio
├── repositories/ # Acesso a dados (SQL)
├── integrations/ # WhatsApp / Email
├── infra/ # Banco, segurança, migrações
├── templates/ # HTML
├── static/ # JS / CSS

---

## 🔐 Autenticação

Utiliza Flask-Login.

- Login protegido por CSRF
- Rate limit simples
- Controle de roles
- Cookies seguros

---

## 🤖 Pipeline de IA

Fluxo estruturado:

Anamnese → Plano Terapêutico → Relatório Científico
Saída:

- JSON validado
- Schemas Pydantic
- Respostas estruturadas

---

## 🚀 Como Executar

### 1️⃣ Criar ambiente virtual

```bash
python -m venv env
env\Scripts\activate
```

Instalar dependências
pip install -r requirements.txt

Configurar variáveis
OPENAI_API_KEY=...
SECRET_KEY=...
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=root
DB_NAME=cannabia

Rodar aplicação

Sempre rodar como pacote:
python -m src.app

Nunca rodar:
python src/app.py

🌐 Rotas Principais
Rota Descrição
/ Dashboard principal
/login Login
/realtime Notificações
/scheduling Agendamentos
/historico Histórico
/ai/test Teste pipeline IA
📦 Camadas do Sistema
Web

Responsável por rotas e renderização.

Services

Regras de negócio.

Repositories

Persistência e SQL.

Integrations

Serviços externos (WhatsApp / Email).

AI

Pipeline clínico estruturado.

🧱 Padrões Utilizados

Application Factory

Blueprints

Service Layer

Repository Pattern

Separation of Concerns

JSON Schema Validation (Pydantic)

📌 Status do Projeto

Arquitetura modular consolidada
Pronto para testes automatizados
Pronto para containerização
Preparado para produção

🧠 Autor

Projeto idealizado e arquitetado com foco em clareza, escalabilidade e evolução contínua.

---

Pronto.  
Isso já coloca seu projeto em nível profissional.

---

# 🧹 4️⃣ Remover definitivamente legacy/

Agora vamos fazer limpo e seguro.

Antes de apagar:

### Confirme que nenhum arquivo importa algo de `legacy`

No PowerShell:

```powershell
Get-ChildItem -Recurse -Filter *.py src | Select-String "legacy"


Se não retornar nada → seguro remover.
```
