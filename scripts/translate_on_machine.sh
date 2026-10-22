#!/usr/bin/env bash
# Run the free NLLB-200 course translation on one machine.
#
#   scripts/translate_on_machine.sh setup           # once: venv + dependencies
#   scripts/translate_on_machine.sh test            # one course, es + km
#   scripts/translate_on_machine.sh run spark       # full batch, Spark share
#   scripts/translate_on_machine.sh run ibuy        # full batch, iBuyPower share
#   scripts/translate_on_machine.sh run all         # every language on this machine
#   scripts/translate_on_machine.sh status          # files written so far
#
# Output: $AOEP_COURSE_TRANSLATION_DIR (default ~/translations). Safe to rerun:
# finished course-languages are skipped. NLLB_DEVICE=cuda|cpu overrides auto.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
OUT="${AOEP_COURSE_TRANSLATION_DIR:-$HOME/translations}"
PORT="${TRANSLATE_PORT:-8002}"
DEMO="audio-intro-to-machine-learning"
SPARK_LANGS="es fr de it pt nl pl ru uk tr ar he hi bn ur fa zh ja ko vi"
IBUY_LANGS="th id sw el cs km"

activate() { [ -f .venv/bin/activate ] && . .venv/bin/activate; }

langs_for() {
  case "${1:-all}" in
    spark) echo "$SPARK_LANGS" ;;
    ibuy)  echo "$IBUY_LANGS" ;;
    all)   echo "$SPARK_LANGS $IBUY_LANGS" ;;
    *) echo "unknown share: $1 (spark|ibuy|all)" >&2; exit 2 ;;
  esac
}

start_gateway() {
  export RATE_LIMIT_DISABLED=1
  if curl -sf "http://127.0.0.1:$PORT/languages" >/dev/null 2>&1; then return; fi
  nohup uvicorn speech_gw.main:app --app-dir services/speech/src --port "$PORT" \
    > "$OUT/gateway.log" 2>&1 &
  for _ in $(seq 1 60); do
    curl -sf "http://127.0.0.1:$PORT/languages" >/dev/null 2>&1 && return
    sleep 1
  done
  echo "speech gateway did not start; see $OUT/gateway.log" >&2; exit 1
}

batch() {
  export SPEECH_BASE_URL="http://127.0.0.1:$PORT" AOEP_COURSE_TRANSLATION_DIR="$OUT"
  python3 scripts/translate_courses_batch.py --audio-only --verbose "$@"
}

cmd="${1:-}"; shift || true
mkdir -p "$OUT"
case "$cmd" in
  setup)
    [ -d .venv ] || python3 -m venv .venv
    activate
    pip install -q -e packages/shared -e services/speech -e subrepos/theodore_audio_translation_lab \
      transformers sentencepiece
    python3 -c "import torch" 2>/dev/null || pip install -q torch
    python3 -c "import torch;print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
    echo "On the DGX Spark install NVIDIA's CUDA build of PyTorch (NGC container) if cuda is False."
    ;;
  test)
    activate; start_gateway
    batch --course "$DEMO" --language es --language km
    ls -l "$OUT/$DEMO"
    ;;
  run)
    activate; start_gateway
    args=()
    for l in $(langs_for "${1:-all}"); do args+=(--language "$l"); done
    batch --concurrency "${CONCURRENCY:-4}" "${args[@]}"
    ;;
  status)
    echo "course folders: $(find "$OUT" -mindepth 1 -maxdepth 1 -type d | wc -l)"
    echo "language files: $(find "$OUT" -mindepth 2 -name '*.json' | wc -l)"
    ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
