#!/usr/bin/env bash
set -euo pipefail

mode="plan"
if [[ "${1:-}" == "--apply" ]]; then
  mode="apply"
fi

conflicts=$(git diff --name-only --diff-filter=U || true)
if [[ -z "$conflicts" ]]; then
  echo "Sem conflitos de merge no momento."
  exit 0
fi

echo "Arquivos com conflito:"
echo "$conflicts"

echo

echo "Política sugerida Cannab'IA:"
echo "- Manter OURS para arquitetura nova e segurança:"
echo "  src/app.py src/auth.py src/config.py src/database.py src/realtime_notifications.py"
echo "  src/security.py src/services/* src/repositories/* src/integrations/* docs/* migrations/* .env.example"
echo "- Revisar manualmente (alto risco):"
echo "  src/templates/* src/dashboard.py src/historico_atendimento.py src/scheduling_chain.py src/webhook.py"

if [[ "$mode" == "plan" ]]; then
  echo
  echo "Modo plano. Para aplicar resolução automática parcial rode:"
  echo "  scripts/conflict_helper.sh --apply"
  exit 0
fi

# Apply partial automatic resolution for low-risk groups
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  case "$f" in
    docs/*|migrations/*|.env.example|src/auth.py|src/config.py|src/database.py|src/realtime_notifications.py|src/security.py|src/app.py|src/services/*|src/repositories/*|src/integrations/*)
      git checkout --ours -- "$f"
      git add "$f"
      echo "[OURS] $f"
      ;;
    *)
      echo "[MANUAL] $f"
      ;;
  esac
done <<< "$conflicts"

echo
echo "Resolução parcial aplicada. Finalize arquivos MANUAL e conclua com:"
echo "  git add <arquivos> && git commit"
