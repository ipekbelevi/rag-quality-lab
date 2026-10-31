#!/usr/bin/env bash
# Run Promptfoo with privacy settings and the project's Python env.
#   ./redteam/run.sh generate              -> redteam/redteam.yaml (attack set, LOCAL mode)
#   MODE=remote ./redteam/run.sh generate  -> also remote-only plugins (needs `npx promptfoo auth login`)
#   ./redteam/run.sh eval <label>          -> replays the attack set, writes redteam/output/<label>.json
# Defenses are chosen with env vars, e.g.:  PROMPT_VARIANT=hardened GUARDRAIL=on ./redteam/run.sh eval hardened
set -euo pipefail
cd "$(dirname "$0")"

export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_SHARING=1
export PROMPTFOO_DISABLE_UPDATE=1
export PROMPTFOO_PYTHON="$PWD/../.venv/bin/python"

config=promptfooconfig.yaml
if [[ "${MODE:-local}" == "remote" ]]; then
  config=promptfooconfig.remote.yaml
else
  # Attacks generated locally with our OpenAI key, not on Promptfoo servers
  export PROMPTFOO_DISABLE_REMOTE_GENERATION=true
fi

case "${1:-}" in
  generate)
    npx promptfoo redteam generate -c "$config" -o redteam.yaml --env-file ../.env --force
    ;;
  eval)
    label="${2:?label required}"
    mkdir -p output
    npx promptfoo redteam eval -c redteam.yaml --env-file ../.env -o "output/$label.json" --no-cache -j 4
    ;;
  *)
    echo "usage: [MODE=remote] $0 generate | $0 eval <label>"; exit 1
    ;;
esac
