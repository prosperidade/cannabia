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

## Quando o conflito persistir: recriar PR do zero (recomendado)

Se o PR continuar com conflito mesmo após resolução local, o problema normalmente é histórico divergente da branch base. Nesse caso, use estratégia de PR limpo:

1. Atualize/tenha a branch base local (ex.: `main`) com o estado mais recente.
2. Crie uma branch nova a partir da base atualizada.
3. Traga apenas os commits necessários via `cherry-pick` (ou reaplique mudanças mínimas).
4. Resolva conflitos pontuais já no cherry-pick.
5. Rode validações (`python -m compileall src`).
6. Abra **novo PR** e feche o anterior.

Exemplo de sequência:

```bash
git checkout main
git pull
git checkout -b fix/pr-clean-reopen
git cherry-pick <commit_1> <commit_2> ...
python -m compileall src
git push origin fix/pr-clean-reopen
```

### Regra para reduzir risco
- Evite carregar commits de tentativa/fix antigo que só mexeram em resolução de conflito.
- Prefira poucos commits funcionais e atômicos.
