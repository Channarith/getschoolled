#!/usr/bin/env bash
# Render the demo narration in a consented voice on the Spark, under gs_run.sh (GPU lock, memory gate, no orphans).
#   scripts/render_demo_voice.sh [--voice channarith] [--shard i/N] [--langs en,es] [--limit N]
# Assets go to $GS_VOICE_ASSETS (default ~/voice-assets). Run again any time: finished clips are skipped.
# Other machines can take shards (e.g. --shard 1/2) and rsync their assets dir back.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ "$(uname -s)" == "Linux" ]] || { echo "GPU voice rendering runs on the Spark (Linux/CUDA), not here." >&2; exit 64; }
PY="${VOXCPM_PY:-$HOME/venvs/voxcpm/bin/python}"
[[ -x "$PY" ]] || { echo "missing $PY (VoxCPM2 venv)" >&2; exit 66; }
export AOEP_REQUIRE_CUDA=1
# VoxCPM2 compiles Triton kernels at load; without Python.h (apt python3.12-dev) that fails, so skip the compile then.
if ! "$PY" -c 'import os,sysconfig,sys; sys.exit(0 if os.path.exists(os.path.join(sysconfig.get_paths()["include"],"Python.h")) else 1)'; then
  export TORCHDYNAMO_DISABLE=1
fi
exec "$ROOT/scripts/gs_run.sh" --name "demo-voice-render" --gpu --timeout 14400 -- \
  env PYTHONPATH="$ROOT:$ROOT/packages/shared/src" "$PY" -m tts_bakeoff.demo_voice.render run "$@"
