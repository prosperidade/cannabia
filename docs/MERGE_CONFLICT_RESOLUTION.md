# Resolução de conflitos do PR atual

Este repositório recebeu conflitos no GitHub nos arquivos:

- `docs/DOCUMENTACAO_SISTEMA.md`
- `src/app.py`
- `src/config.py`
- `src/dashboard.py`
- `src/historico_atendimento.py`
- `src/realtime_notifications.py`
- `src/scheduling_chain.py`
- `src/templates/scheduling_dashboard.html`

## Decisão adotada

Para preservar a arquitetura em camadas e os controles P0 de segurança já implementados, a política padrão é **manter OURS** nesses arquivos durante a resolução.

## Como executar localmente

1. Trazer a branch base do PR (`git fetch` + merge/rebase).
2. Rodar:
   - `scripts/resolve_conflicts_now.sh`
3. Validar:
   - `python -m compileall src`
4. Finalizar:
   - `git commit -m "Resolve conflitos do PR"`

## Observação

Neste ambiente de automação não há branch remota configurada para reproduzir o conflito do GitHub diretamente, então o script foi preparado para aplicação imediata quando o merge/rebase com a base do PR for feito localmente.
