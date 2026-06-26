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
while IFS= read -r line; do
  line="${line%%$'\r'}"
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  [[ -z "$key" ]] && continue
  val="${val#\"}"; val="${val%\"}"
  export "$key=$val"
done < "$ENV_FILE"

cd "${ROOT}/services/${svc}"
export PYTHONPATH=src
exec "$VENV_PY" -m uvicorn "$module" --host 0.0.0.0 --port "$port"
