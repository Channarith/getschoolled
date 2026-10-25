#!/usr/bin/env bash
# Read-only preflight for the voice-clone models on the Spark: which of VoxCPM2 / CosyVoice 2 can run, and what to fix.
#   scripts/check_clone_models.sh
# Also prints the tail of the last clone logs (the synth-*.log files) so a failed run can be read from one place.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COSY="${COSYVOICE_REPO:-$HOME/code/CosyVoice}"
export PYTHONPATH="$ROOT:$ROOT/packages/shared/src" COSYVOICE_REPO="$COSY" COSYVOICE_MODEL_DIR="${COSYVOICE_MODEL_DIR:-$COSY/pretrained_models/CosyVoice2-0.5B}"
VOX_PY="${VOXCPM_PY:-$HOME/venvs/voxcpm/bin/python}"
if [[ -x "$VOX_PY" ]]; then "$VOX_PY" -m tts_bakeoff.voice_clone.doctor --model voxcpm2; else echo "voxcpm2: NOT READY: missing $VOX_PY"; fi
COSY_PY="$COSY/.venv/bin/python"
if [[ -x "$COSY_PY" ]]; then PYTHONPATH="$PYTHONPATH:$COSY:$COSY/third_party/Matcha-TTS" "$COSY_PY" -m tts_bakeoff.voice_clone.doctor --model cosyvoice2
else PYTHONPATH="$PYTHONPATH" python3 -m tts_bakeoff.voice_clone.doctor --model cosyvoice2 2>/dev/null || echo "cosyvoice2: NOT READY: missing $COSY_PY (see the fix lines above or docs/voice-cloning.txt)"; fi
for f in "$ROOT"/runs/*-clones/synth-*.log; do [[ -f "$f" ]] || continue; echo "== $f ($(wc -c < "$f") bytes)"; tail -n 6 "$f" | cut -c1-200; done
