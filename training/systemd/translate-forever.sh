#!/usr/bin/env bash
# Resume the 222-course NLLB batch after a reboot.
# CPU only, concurrency 1, so the STEM exam keeps the GPU.
# Does not start Khmer CosyVoice.
set -u
ROOT="/home/nvidia/code/gs-wt/spark-eval-gates"
PY="/home/nvidia/code/getschoolled/.venv/bin/python"
cd "$ROOT"
export SPEECH_BASE_URL="http://127.0.0.1:8002"
export AOEP_COURSE_TRANSLATION_DIR="${AOEP_COURSE_TRANSLATION_DIR:-$HOME/.cache/aoep/course_translations}"
export TRANSLATION_TIMEOUT_S="${TRANSLATION_TIMEOUT_S:-180}"
export RATE_LIMIT_DISABLED=1
export NLLB_DEVICE=cpu
export NLLB_MODEL="${NLLB_MODEL:-facebook/nllb-200-distilled-600M}"
export PYTHONPATH="$ROOT/packages/shared/src${PYTHONPATH:+:$PYTHONPATH}"

nllb_pid=""
cleanup() {
  if [[ -n "$nllb_pid" ]] && kill -0 "$nllb_pid" 2>/dev/null; then
    kill "$nllb_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

start_nllb() {
  if curl -sf -m 3 "$SPEECH_BASE_URL/languages" >/dev/null 2>&1; then
    echo "=== nllb already up $(date -Is) ==="
    return 0
  fi
  echo "=== starting nllb on cpu $(date -Is) ==="
  "$PY" -m uvicorn speech_gw.main:app \
    --app-dir "$ROOT/services/speech/src" \
    --host 127.0.0.1 --port 8002 &
  nllb_pid=$!
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 15 20 25 30; do
    if curl -sf -m 3 "$SPEECH_BASE_URL/languages" >/dev/null 2>&1; then
      echo "=== nllb up pid=$nllb_pid $(date -Is) ==="
      return 0
    fi
    sleep 1
  done
  echo "=== nllb did not answer $(date -Is) ==="
  return 1
}

wait_for_memory() {
  local need_mb="${AOEP_TRANSLATE_MIN_FREE_MB:-12288}" free_mb
  local _
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
    free_mb="$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)"
    if [[ -z "$free_mb" || "$free_mb" -ge "$need_mb" ]]; then
      echo "=== translate memory ok free_mb=${free_mb} $(date -Is) ==="
      return 0
    fi
    echo "=== translate waiting free_mb=${free_mb} need_mb=${need_mb} $(date -Is) ==="
    sleep 20
  done
}

while true; do
  wait_for_memory
  if ! start_nllb; then
    sleep 60
    continue
  fi
  echo "=== translate batch start $(date -Is) ==="
  "$PY" scripts/translate_courses_batch.py --audio-only --concurrency 1 --verbose \
    --language es --language fr --language de --language it --language pt \
    --language nl --language pl --language ru --language uk --language tr \
    --language ar --language he --language hi --language bn --language ur \
    --language fa --language zh --language ja --language ko --language vi \
    --language yue
  echo "=== translate batch exit=$? $(date -Is) ==="
  sleep 60
done
