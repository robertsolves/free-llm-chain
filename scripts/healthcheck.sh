#!/usr/bin/env bash
# Calls every model group in config.yaml directly through the LiteLLM proxy and prints OK or FAIL for each.
# A FAIL that says 429 or "quota" is a used-up daily pool, not a broken model: check it after the reset.
# Fallback test: put a bad GEMINI_API_KEY in .env, restart the proxy, and run with --chain:
# the `coder` request should still succeed through the next model.
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && . ./.env; set +a
BASE="${LITELLM_BASE_URL:-http://127.0.0.1:4000}"
MODELS=($(sed -n 's/^ *- model_name: *\([^ ]*\).*/\1/p' config.yaml))
[[ "${1:-}" == "--chain" ]] && MODELS=(coder pipeline)

status=0
for m in "${MODELS[@]}"; do
  # Calling a group directly must not fall through to the next one, or a dead model would look OK.
  extra=',"disable_fallbacks":true'
  [[ "${1:-}" == "--chain" ]] && extra=''
  body="{\"model\":\"${m}\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word OK.\"}],\"max_tokens\":20${extra}}"
  resp=$(curl -sS -m 60 "${BASE}/v1/chat/completions" \
    -H "Authorization: Bearer ${LITELLM_MASTER_KEY:-}" -H "Content-Type: application/json" --data-raw "${body}" 2>&1)
  served=$(printf '%s' "${resp}" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print(d["model"] if d.get("choices") else "")
except Exception: print("")')
  if [[ -n "${served}" ]]; then
    echo "OK    ${m} (served by ${served})"
  else
    echo "FAIL  ${m}: $(printf '%s' "${resp}" | head -c 200)"
    status=1
  fi
done
exit ${status}
