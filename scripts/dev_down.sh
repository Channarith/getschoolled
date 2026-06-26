#!/usr/bin/env bash
# Stop the local AI Classroom stack started by scripts/dev_up.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS="$ROOT/logs"

stopped=0
for pidf in "$LOGS"/*.pid; do
  [ -f "$pidf" ] || continue
  name="$(basename "$pidf" .pid)"
  pid="$(cat "$pidf" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    # kill the process group so uvicorn/next children also stop
    kill "$pid" 2>/dev/null || true
    pkill -P "$pid" 2>/dev/null || true
    printf "  stopped %s (pid %s)\n" "$name" "$pid"
    stopped=$((stopped+1))
  fi
  rm -f "$pidf"
done
[ "$stopped" = 0 ] && echo "Nothing was running (no PID files in logs/)." || echo "Stopped $stopped process(es)."
