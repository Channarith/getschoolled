#!/usr/bin/env bash
# Start one AOEP backend service locally with config/local.env loaded.
# Usage: ./scripts/run_local_service.sh <service> [port]
#
# Examples:
#   ./scripts/run_local_service.sh identity
#   ./scripts/run_local_service.sh memory 8004
#   ./scripts/run_local_service.sh orchestrator 8000

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/config/local.env"
VENV_PY="${ROOT}/.venv/bin/python3"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi
if [[ ! -x "$VENV_PY" ]]; then
  echo "run 'make install' first (missing $VENV_PY)" >&2
  exit 1
fi

svc="${1:-}"
if [[ -z "$svc" ]]; then
  echo "usage: $0 <service> [port]" >&2
  echo "  identity orchestrator memory curriculum billing integrations speech perception" >&2
  exit 1
fi

declare -A PORTS=(
  [orchestrator]=8000
  [speech]=8002
  [perception]=8003
  [memory]=8004
  [curriculum]=8005
  [billing]=8006
  [integrations]=8007
  [identity]=8008
)

declare -A MODULES=(
  [orchestrator]=orchestrator.main:app
  [speech]=speech_gw.main:app
  [perception]=perception.main:app
  [memory]=memory.main:app
  [curriculum]=curriculum.main:app
  [billing]=billing.main:app
  [integrations]=integrations.main:app
  [identity]=identity.main:app
)

port="${2:-${PORTS[$svc]:-}}"
module="${MODULES[$svc]:-}"
if [[ -z "$port" || -z "$module" ]]; then
  echo "unknown service: $svc" >&2
  exit 1
fi

# Docker-style KEY=VALUE files may contain characters bash `source` cannot parse.
# Never overwrite a non-empty env; never apply empty values (blank XAI_API_KEY=
# must not clear a real key injected by the shell / secrets manager).
while IFS= read -r line; do
  line="${line%%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  [[ -z "$key" ]] && continue
  val="${val#\"}"; val="${val%\"}"
  val="${val#\'}"; val="${val%\'}"
  if [[ -n "${!key:-}" ]]; then
    continue
  fi
  if [[ -z "$val" ]]; then
    continue
  fi
  export "$key=$val"
done < "$ENV_FILE"

# Soft-upgrade blank / retired Grok chat models
case "${XAI_MODEL:-}" in
  ""|grok-2|grok-2-1212|grok-2-latest|grok-beta|grok-4)
    export XAI_MODEL=grok-4.3
    ;;
esac
case "${XAI_TEXT_MODEL:-}" in
  ""|grok-2|grok-2-1212|grok-2-latest|grok-beta|grok-3-latest|grok-4)
    export XAI_TEXT_MODEL=grok-4.3
    ;;
esac

# config/local.env carries the compose LiveKit hostname (ws://livekit:7880),
# which doesn't resolve for a native run. Point at localhost so tokens the
# orchestrator mints target the local `make run-livekit` server.
case "${LIVEKIT_URL:-}" in
  *//livekit:*) export LIVEKIT_URL="ws://localhost:7880" ;;
esac

# Same for in-cluster speech hostname when running natively.
case "${SPEECH_BASE_URL:-}" in
  *//speech:*) export SPEECH_BASE_URL="http://127.0.0.1:8002" ;;
esac

cd "${ROOT}/services/${svc}"
export PYTHONPATH=src
echo "[run_local_service] svc=$svc port=$port XAI_API_KEY=$([ -n "${XAI_API_KEY:-}" ] && echo set || echo missing) ELEVENLABS_API_KEY=$([ -n "${ELEVENLABS_API_KEY:-}" ] && echo set || echo missing) XAI_MODEL=${XAI_MODEL:-} SPEECH_BASE_URL=${SPEECH_BASE_URL:-}"
exec "$VENV_PY" -m uvicorn "$module" --host 0.0.0.0 --port "$port"
