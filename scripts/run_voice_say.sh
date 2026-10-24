#!/usr/bin/env bash
# Speak one sentence in an enrolled, consented voice on the Spark, under gs_run.sh (GPU lock, memory gate, no orphans).
#   scripts/run_voice_say.sh MODEL SPEAKER LANG OUT.wav TEXTFILE      (GS_VOICES_DIR overrides ~/voices)
# VoxCPM2 compiles GPU kernels with Triton, which needs Python.h; without the headers (apt install python3.12-dev) compiling
# is switched off with TORCHDYNAMO_DISABLE=1: slower but it works.
set -euo pipefail
[[ $# -eq 5 ]] || { echo "usage: $0 MODEL SPEAKER LANG OUT.wav TEXTFILE" >&2; exit 64; }
MODEL="$1"; SPEAKER="$2"; LANG_CODE="$3"; OUT="$4"; TEXTFILE="$5"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COSY="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
[[ "$(uname -s)" == "Linux" ]] || { echo "GPU voice cloning runs on the Spark (Linux/CUDA), not here." >&2; exit 64; }
case "$MODEL" in
  voxcpm2)    PY="$HOME/venvs/voxcpm/bin/python"; EXTRA="" ;;
  cosyvoice2) PY="$COSY/.venv/bin/python"; EXTRA="$COSY:$COSY/third_party/Matcha-TTS" ;;
  *) echo "unknown model $MODEL" >&2; exit 64 ;;
esac
[[ -x "$PY" ]] || { echo "no Python at $PY" >&2; exit 66; }
if ! "$PY" -c 'import os,sys,sysconfig; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_paths()["include"], "Python.h")) else 1)'; then
  export TORCHDYNAMO_DISABLE=1
fi
export AOEP_REQUIRE_CUDA=1
exec "$ROOT/scripts/gs_run.sh" --name "say-$MODEL-$SPEAKER" --gpu --timeout 900 -- \
  env PYTHONPATH="$ROOT:$ROOT/packages/shared/src:$EXTRA" "$PY" -m tts_bakeoff.voice_clone.bakeoff say \
  --speaker "$SPEAKER" --model "$MODEL" --lang "$LANG_CODE" --text-file "$TEXTFILE" --out "$OUT"
