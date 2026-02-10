# Playbook de Resolução de Conflitos (Cannab'IA)

Se o PR apresentar conflito em muitos arquivos, use este fluxo:

1. Verifique conflitos atuais:
   - `git diff --name-only --diff-filter=U`

2. Gere plano de resolução por política do repositório:
   - `scripts/conflict_helper.sh`

3. Aplique resolução automática parcial (apenas arquivos de baixo risco):
   - `scripts/conflict_helper.sh --apply`

4. Resolva manualmente arquivos críticos de rota/template:
   - `src/templates/*`
   - `src/dashboard.py`
   - `src/historico_atendimento.py`
   - `src/scheduling_chain.py`
   - `src/webhook.py`

5. Valide build:
   - `python -m compileall src`

6. Finalize:
   - `git add .`
   - `git commit -m "Resolve conflitos de merge"`

## Regra prática de decisão
- **Ours**: arquitetura em camadas (`services/repositories/integrations`), segurança (`auth/security`), docs e migrações.
- **Manual**: templates e rotas que mudam comportamento de UX/segurança simultaneamente.

## Observação
Este helper não substitui revisão humana; ele reduz trabalho repetitivo e evita perder os controles de segurança implementados.
