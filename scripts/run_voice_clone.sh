#!/usr/bin/env bash
# Run the consent-gated voice-clone bake-off on the DGX Spark, one model at a time, under gs_run.sh
# (memory cap, GPU lock, no orphans). Never run on the Mac.
#
#   scripts/run_voice_clone.sh [OUT_DIR] [extra bakeoff args...]
#   VOICES: GS_VOICES_DIR (default ~/voices)   COSYVOICE_REPO (default ~/code/CosyVoice)   LANGS (default en,es,zh,yue,vi,th,km,sw,hi; yue = VoxCPM2 only)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/runs/$(date +%F)-clones}"; shift || true
EXTRA=("$@")
LANGS="${LANGS:-en,es,zh,yue,vi,th,km,sw,hi}"
MODELS="${MODELS:-voxcpm2,cosyvoice2}"   # comma list; the enrollment UI runs one model at a time
COSY="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
[[ "$(uname -s)" == "Linux" ]] || { echo "GPU voice cloning runs on the Spark (Linux/CUDA), not here." >&2; exit 64; }
export AOEP_REQUIRE_CUDA=1
run_model() {  # model venv-python extra-pythonpath
  "$ROOT/scripts/gs_run.sh" --name "voice-clone-$1" --gpu --timeout 7200 -- \
    env PYTHONPATH="$ROOT:$ROOT/packages/shared/src:$3" "$2" -m tts_bakeoff.voice_clone.bakeoff run \
    --out "$OUT" --models "$1" --langs "$LANGS" ${EXTRA[@]+"${EXTRA[@]}"}
}
want() { [[ ",$MODELS," == *,"$1",* ]]; }
VOX_PY="$HOME/venvs/voxcpm/bin/python"
if want voxcpm2; then
  if [[ -x "$VOX_PY" ]]; then run_model voxcpm2 "$VOX_PY" ""; else echo "skip voxcpm2: no $VOX_PY"; fi
fi
COSY_PY="$COSY/.venv/bin/python"
if want cosyvoice2; then
  if [[ -x "$COSY_PY" ]]; then run_model cosyvoice2 "$COSY_PY" "$COSY:$COSY/third_party/Matcha-TTS"; else echo "skip cosyvoice2: no $COSY_PY"; fi
fi
echo "done. Listen: python3 -m tts_bakeoff.lab --out $OUT"
