#!/usr/bin/env bash
set -euo pipefail
LOG_DIR="${A2F_LOOP_LOG_DIR:-/tmp/a2f_cosyvoice_loop}"
for name in loop a2f_stub cosyvoice; do
  pidfile="$LOG_DIR/${name}.pid"
  if [[ -f "$pidfile" ]]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name pid=$pid"
      kill "$pid" || true
    fi
    rm -f "$pidfile"
  fi
done
docker rm -f a2f-nim 2>/dev/null || true
echo "Stopped (logs kept under $LOG_DIR)"
