#!/usr/bin/env bash
# Launcher for the Spark memory/GPU balance monitor. All logic is in aoep_shared/spark_balance.py (tested).
#
# Environment (all optional; defaults in spark_balance.Config):
#   BALANCE_FREE_LOW_MB   pause the ingest below this MemAvailable (10240)    BALANCE_FREE_OK_MB   resume above (16384)
#   BALANCE_KILL_FLOOR_MB a starved bake-off may be stopped during a fine-tune only below this (24576)
#   BALANCE_CRITICAL_MB   below this it may be stopped even during an evaluation (6144)
#   BALANCE_WINDOW_S      decode-rate window, started at the first decoded token (180)
#   BALANCE_STARVE_TOK_S  starved below this many tokens/second over the window (0.25)
#   BALANCE_GRACE_S       no kills for this long after the llama-server wakes (600)
#   BALANCE_LLAMA_URL     (http://127.0.0.1:8342)   BALANCE_BAKEOFF_PATTERN  regex of bake-off client command lines
#   BALANCE_DIR           state + logs (~/.local/share/aoep-train)
# Usage: gpu-balance-monitor.sh [--once]
set -u
ROOT="${AOEP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
PY="${AOEP_VENV:-${HOME}/code/getschoolled/.venv}/bin/python"
[ -x "${PY}" ] || PY="$(command -v python3)"
export PYTHONPATH="${ROOT}/packages/shared/src${PYTHONPATH:+:${PYTHONPATH}}"
exec "${PY}" -m aoep_shared.spark_balance "$@"
