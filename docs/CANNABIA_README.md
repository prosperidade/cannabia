# CANNABIA - Plataforma de Inteligência Artificial para Cannabis Medicinal

## Visão Geral do Sistema
O **CannabIA** é um ecossistema médico avançado em desenvolvimento (multi-tenant), projetado especificamente para acolhimento, anamnese e suporte clínico no tratamento com Cannabis Medicinal.

A plataforma atua como um assistente de inteligência artificial de alta especialização, integrado diretamente ao WhatsApp do paciente. Através de um backend robusto escrito em Python (Flask) e de um banco de dados relacional PostgreSQL, o sistema gerencia todo o fluxo do paciente — desde o primeiro contato até a recomendação embasada de planos terapêuticos e o monitoramento contínuo.

## Missão do Médico Especialista Sênior (Persona IA)
No núcleo da inteligência artificial do sistema atua uma persona configurada através de Engenharia de Prompts rigorosa: **o Médico Especialista Sênior**.

Com a identidade de um profissional com 20 anos de experiência clínica em canabinoides, a missão da IA é tripla:
1. **Acolhimento Empático e Estruturado:** Conduzir anamneses precisas via WhatsApp, extraindo queixas principais, histórico de saúde, alergias e medicações em uso de forma natural e sem fricção para o paciente.
2. **Segurança Clínica (Red Flags):** Identificar prontamente potenciais riscos de interações medicamentosas ou condições pré-existentes que demandem atenção imediata.
3. **Embasamento Científico (Medicina Baseada em Evidências):** Cruzar os achados clínicos do paciente com bancos de artigos científicos reais (via RAG - Retrieval-Augmented Generation) para sugerir aos médicos responsáveis planos terapêuticos sólidos, sugerindo proporções ideais de fitocanabinoides (CBD:THC), dosagens escalonadas e vias de administração, com suas respectivas fontes e DOIs científicas.

## Como o Sistema Ajuda no Acolhimento e Suporte Médico via WhatsApp
O WhatsApp é a interface principal do paciente, democratizando o acesso e removendo a barreira tecnológica de baixar aplicativos adicionais. O suporte é prestado no seguinte formato:

- **Contato Inicial Automático:** O webhook da Meta (WhatsApp Business API) recebe as mensagens enviadas pelos pacientes.
- **Isolamento de Dados (Multi-Tenancy):** Logo na recepção, o sistema identifica de qual clínica o paciente pertence (através da amarração do número ou webhook específico) utilizando a arquitetura Tenant (campo `clinic_id`).
- **Pipeline Clínico de IA (3 Etapas):**
  1. O texto livre e denso do WhatsApp é transformado em dados médicos estruturados (Anamnese) via OpenAI (`gpt-4o-mini`).
  2. A IA gera um Plano Terapêutico inicial baseado nos sintomas e patologias identificadas.
  3. O sistema realiza buscas semânticas em uma base vetorial (ChromaDB) de artigos científicos, e um relatório final é gerado (Google Gemini 1.5 Flash), chancelando as condutas sugeridas.
- **Resposta e Monitoramento:** Os resultados e o acompanhamento (monitoramento de eficácia, lembretes de retorno) podem ser ativados através do envio estruturado de mensagens de template ou texto (via `src/integrations/whatsapp.py`), fechando o ciclo do cuidado contínuo.

## Situação Atual do Projeto
O sistema encontra-se ativo e estável:
- ✅ Backend Flask operante com multi-tenancy configurado e seguro (`Flask-Login`, proteção CSRF, isolamento por banco).
- ✅ Integração do Webhook da Meta (WhatsApp) funcional, recebendo e processando eventos com validação HMAC.
- ✅ Pipeline clínico robusto com OpenAI (GPT-4o-mini) e Google Gemini implementado.
- ✅ Banco de Dados relacional PostgreSQL ativo e pronto para escala (migrações aplicadas, utilizando colunas dinâmicas em `JSONB`).
- ⚠️ Pipeline de Integração de artigos científicos (RAG): O banco vetorial (ChromaDB) e o código já existem; foco atual na ingestão contínua de bibliotecas científicas na base (PubMed/Cochrane).

---
*Documento gerado a partir da inspeção técnica real do ambiente. Para a estrutura técnica do código e banco de dados, consulte o documento `TECHNICAL_CONTEXT.md`.*