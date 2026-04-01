# Sprint 2 Backlog

## Objetivo

Formalizar a jornada clínica inicial da CannabIA com timeline do paciente, estados de caso e base para prontuário longitudinal, aproveitando a foundation já criada em `tenant`.

## Épico A — Jornada do paciente

| ID | Story técnica | Arquivos principais | Resultado esperado | Prioridade |
| --- | --- | --- | --- | --- |
| A1 | Consolidar estados explícitos da jornada do paciente | `src/services/anamnesis_flow.py`, `src/repositories/patient_timeline_repository.py`, `migrations/005_patient_timeline_foundation.sql` | Eventos e estágios mínimos padronizados | Alta |
| A2 | Criar vínculo operacional entre anamnese, atendimento e agendamento | `src/repositories/anamnesis_repository.py`, `src/repositories/appointment_repository.py`, `src/services/appointment_service.py` | Paciente com trilha longitudinal básica | Alta |
| A3 | Preparar entrada para documentos e aceite operacional | `src/web/routes/atendimentos.py`, `src/templates/atendimentos_detail.html`, futura migration de anexos | Backlog técnico da próxima etapa fechado | Média |

## Épico B — Jornada do médico

| ID | Story técnica | Arquivos principais | Resultado esperado | Prioridade |
| --- | --- | --- | --- | --- |
| B1 | Tornar o detalhe do atendimento a visão inicial do caso | `src/web/routes/atendimentos.py`, `src/templates/atendimentos_detail.html` | Página com contexto longitudinal mínimo | Alta |
| B2 | Definir transições clínicas mínimas após revisão | `src/repositories/anamnesis_repository.py`, `src/repositories/patient_timeline_repository.py` | Revisão médica refletida na timeline | Alta |
| B3 | Mapear próximas ações do médico para prontuário | `docs/16_CURRENT_SYSTEM_INVENTORY.md`, `docs/18_SPRINT_2_BACKLOG.md` | Ordem de evolução documentada | Média |

## Épico C — Prontuário e timeline

| ID | Story técnica | Arquivos principais | Resultado esperado | Prioridade |
| --- | --- | --- | --- | --- |
| C1 | Criar tabela e repositório base de timeline do paciente | `migrations/005_patient_timeline_foundation.sql`, `src/repositories/patient_timeline_repository.py` | Timeline persistida e consultável | Alta |
| C2 | Backfill inicial de eventos existentes | `migrations/005_patient_timeline_foundation.sql` | Histórico mínimo reaproveitado sem retrabalho manual | Alta |
| C3 | Desenhar a próxima migration de prontuário longitudinal | futura `migrations/006_*`, `docs/08_DATABASE_AND_DOMAIN_MODEL.md` | Blueprint da próxima fase | Média |

## Épico D — Segurança e consistência

| ID | Story técnica | Arquivos principais | Resultado esperado | Prioridade |
| --- | --- | --- | --- | --- |
| D1 | Corrigir uso inconsistente de CSRF nos formulários | `src/web/routes/auth.py`, `src/templates/*.html` | Validação funcional e compatível com legado | Alta |
| D2 | Validar compile e smoke test local das rotas tocadas | `src/services/*.py`, `src/web/routes/*.py` | Base apta para teste manual | Alta |
| D3 | Atualizar inventário e diário operacional ao fim de cada bloco | `docs/progresso1.md`, `docs/16_CURRENT_SYSTEM_INVENTORY.md` | Rastro documental contínuo | Alta |

## Ordem recomendada de execução

1. Fechar foundation da timeline e backfill inicial.
2. Integrar eventos em anamnese, revisão clínica e agendamento.
3. Expor a timeline no detalhe do atendimento.
4. Validar consistência de CSRF e compile local.
5. Desenhar a próxima fase de prontuário longitudinal.
