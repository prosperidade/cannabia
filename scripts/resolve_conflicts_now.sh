#!/usr/bin/env bash
set -euo pipefail

# Resolve exactly the files reported by GitHub conflict message.
FILES=(
  docs/DOCUMENTACAO_SISTEMA.md
  src/app.py
  src/config.py
  src/dashboard.py
  src/historico_atendimento.py
  src/realtime_notifications.py
  src/scheduling_chain.py
  src/templates/scheduling_dashboard.html
)

if [[ -z "$(git diff --name-only --diff-filter=U || true)" ]]; then
  echo "Sem conflitos locais no momento."
  echo "Se o conflito estiver no GitHub, rode este script após fazer merge/rebase da branch base localmente."
  exit 0
fi

for f in "${FILES[@]}"; do
  if git ls-files -u -- "$f" | grep -q .; then
    # Política atual: manter versão da branch de trabalho para preservar arquitetura e segurança P0.
    git checkout --ours -- "$f"
    git add "$f"
    echo "Resolvido (ours): $f"
  fi
done

echo "Conflitos restantes:"
git diff --name-only --diff-filter=U || true
