#!/usr/bin/env bash
# Translate the driver's ed demo on one machine. Finished lines are skipped.
#
#   scripts/translate_drivers_ed.sh mac      Spanish and French, CPU, on this Mac
#   scripts/translate_drivers_ed.sh spark    the long share, on the GPU
#   scripts/translate_drivers_ed.sh kalel    Thai, Indonesian, Swahili, Greek, Czech; 8 GB profile
#
# Does not touch the course-translation gateway on port 8002. On the Spark that
# gateway is already busy; this job uses the free GPU instead.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SHARE="${1:?usage: translate_drivers_ed.sh mac|spark|kalel}"
# The project venv on this Mac has no PyTorch. Use the first interpreter that does.
PY=""
for cand in ${AOEP_PYTHON:+"$AOEP_PYTHON"} "$ROOT/.venv/bin/python" \
  "$HOME/code/getschoolled/.venv/bin/python" \
  "$HOME/code/trading/000_trading/venv/bin/python" "$(command -v python3 || true)"; do
  [ -n "$cand" ] && [ -x "$cand" ] || continue
  if "$cand" -c 'import torch' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "no python with torch. On this Mac that is ~/code/trading/000_trading/venv." >&2
  exit 1
fi
echo "python: $PY"
case "$SHARE" in
  mac)
    export AOEP_ALLOW_CPU=1 NLLB_DEVICE=cpu
    export NLLB_MODEL="${NLLB_MODEL:-facebook/nllb-200-distilled-600M}"
    export NLLB_BATCH_SIZE="${NLLB_BATCH_SIZE:-4}"
    # Beam search of 4 on a CPU makes a two-language demo take all day.
    export NLLB_NUM_BEAMS="${NLLB_NUM_BEAMS:-1}"
    # This Mac's project venv has no torch. sentencepiece for the interpreter
    # in AOEP_PYTHON lives here when that interpreter is used.
    if [ -d "$ROOT/.cache/py-extra" ]; then
      export PYTHONPATH="$ROOT/.cache/py-extra${PYTHONPATH:+:$PYTHONPATH}"
    fi
    export HF_HOME="${HF_HOME:-$ROOT/.cache/huggingface}"
    export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"
    GPU=()
    ;;
  spark)
    # 600M is already on the Spark from the CPU catalog translator. This job
    # loads its own copy on the free GPU and does not open port 8002.
    unset NLLB_PROFILE || true
    export NLLB_MODEL="${NLLB_MODEL:-facebook/nllb-200-distilled-600M}"
    export NLLB_DEVICE="${NLLB_DEVICE:-cuda}"
    export NLLB_BATCH_SIZE="${NLLB_BATCH_SIZE:-8}"
    GPU=(--gpu)
    ;;
  kalel)
    # The 8 GB profile picks the 1.3B model. A leftover NLLB_MODEL would override it.
    unset NLLB_MODEL || true
    export NLLB_PROFILE="${NLLB_PROFILE:-8gb}"
    export NLLB_DEVICE="${NLLB_DEVICE:-cuda}"
    export NLLB_BATCH_SIZE="${NLLB_BATCH_SIZE:-8}"
    GPU=(--gpu)
    ;;
  *) echo "unknown share: $SHARE (mac|spark|kalel)" >&2; exit 2 ;;
esac
# The Spark checkout's gs_run is older and rejects --priority. Pass a flag only
# when that copy understands it. CUDA is still requested via NLLB_DEVICE.
GS="$ROOT/scripts/gs_run.sh"
gs_has() { grep -q -F -e "$1" "$GS"; }
args=(--name "drivers-ed-${SHARE}")
if gs_has --priority; then args+=(--priority background); fi
if gs_has --timeout; then args+=(--timeout "${TIMEOUT_S:-86400}"); fi
if [ "${#GPU[@]}" -gt 0 ] && gs_has --gpu; then args+=(--gpu); fi
exec "$GS" "${args[@]}" -- \
  "$PY" "$ROOT/scripts/translate_drivers_ed.py" --share "$SHARE"
