#!/usr/bin/env bash
# gs_worker.sh - start the fleet worker for THIS machine (what the systemd unit runs).
#
#   scripts/gs_worker.sh                 run the worker loop
#   scripts/gs_worker.sh --once          one tick, then exit (try it by hand)
#   scripts/gs_worker.sh status          shorthand for fleet/queue.py status (and any other queue.py command)
#
# The worker keeps this machine busy with the right jobs, each one started through scripts/gs_run.sh
# (memory/CPU limits, GPU lock, whole-tree cleanup). See docs/ops-schedule.txt.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${GS_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in "$ROOT/.venv/bin/python" "$HOME/code/getschoolled/.venv/bin/python" "$HOME/getschoolled/.venv/bin/python"; do
    [ -x "$c" ] && PY="$c" && break
  done
fi
PY="${PY:-python3}"
export GS_PYTHON="$PY"
case "${1:-worker}" in
  --once) shift; exec "$PY" "$ROOT/scripts/fleet/queue.py" worker --once "$@" ;;
  worker|"") shift 2>/dev/null; exec "$PY" "$ROOT/scripts/fleet/queue.py" worker "$@" ;;
  *) exec "$PY" "$ROOT/scripts/fleet/queue.py" "$@" ;;
esac
