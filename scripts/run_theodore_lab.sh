#!/usr/bin/env bash
# Start one Theodore lab with config/local.env (+ optional .env.local) loaded.
# Usage: scripts/run_theodore_lab.sh <lab> [port]
# Labs: audio_translation | course_studio | webcam | children | homework | music | drive | rag | llm
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAB="${1:-}"
PORT_OVERRIDE="${2:-}"

if [[ -z "$LAB" ]]; then
  echo "Usage: $0 <lab> [port]" >&2
  echo "  labs: audio_translation course_studio webcam children homework music drive rag llm" >&2
  exit 2
fi

# shellcheck disable=SC1091
if [[ -f "$ROOT/scripts/lib/load_env.sh" ]]; then
  # Prefer shared loader when present
  :
fi

load_env_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local key="${BASH_REMATCH[1]}"
      local val="${BASH_REMATCH[2]}"
      val="${val%\"}"; val="${val#\"}"
      val="${val%\'}"; val="${val#\'}"
      # Never overwrite a non-empty env; never apply empty values
      # (blank XAI_API_KEY= must not clear a real key).
      if [[ -n "${!key:-}" ]]; then
        continue
      fi
      if [[ -z "$val" ]]; then
        continue
      fi
      export "$key=$val"
    fi
  done < "$f"
}

load_env_file "$ROOT/config/local.env"
load_env_file "$ROOT/.env.local"

# Soft-upgrade blank / retired text models
case "${XAI_MODEL:-}" in
  ""|grok-2|grok-2-1212|grok-beta)
    export XAI_MODEL=grok-4.3
    ;;
esac

declare -A LAB_PKG=(
  [audio_translation]=theodore_audio_translation_lab
  [course_studio]=theodore_course_studio_lab
  [webcam]=theodore_webcam_lab
  [children]=theodore_children_webcam_lab
  [homework]=theodore_homework_lab
  [music]=theodore_music_lab
  [drive]=theodore_drive_lab
  [rag]=theodore_rag_lab
  [llm]=theodore_llm_lab
)
declare -A LAB_PORT=(
  [audio_translation]=8011
  [course_studio]=8012
  [webcam]=8013
  [children]=8018
  [homework]=8014
  [music]=8015
  [drive]=8016
  [rag]=8017
  [llm]=8019
)

PKG="${LAB_PKG[$LAB]:-}"
DEFAULT_PORT="${LAB_PORT[$LAB]:-}"
if [[ -z "$PKG" || -z "$DEFAULT_PORT" ]]; then
  echo "Unknown lab: $LAB" >&2
  exit 2
fi
PORT="${PORT_OVERRIDE:-$DEFAULT_PORT}"

VENV_PY="${ROOT}/.venv/bin/python3"
if [[ ! -x "$VENV_PY" ]]; then
  VENV_PY="python3"
fi

export PYTHONPATH="${ROOT}/subrepos/${PKG}/src:${ROOT}/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}"

echo "[run_theodore_lab] lab=$LAB pkg=$PKG port=$PORT XAI_API_KEY=$([ -n "${XAI_API_KEY:-}" ] && echo set || echo missing) ELEVENLABS_API_KEY=$([ -n "${ELEVENLABS_API_KEY:-}" ] && echo set || echo missing) XAI_MODEL=${XAI_MODEL:-}"

exec "$VENV_PY" -m uvicorn "${PKG}.main:app" --host 0.0.0.0 --port "$PORT" --reload
