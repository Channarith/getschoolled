#!/usr/bin/env bash
# Stop stale Metro/Expo dev servers (fixes port 8081 prompts and frozen starts).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORTS="${MOBILE_METRO_PORTS:-8081 8082 8083}"

kill_port() {
  local port="$1"
  local pids=""
  if command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  fi
  if [ -z "$pids" ]; then
    return 0
  fi
  echo "==> Stopping process on port $port (pid $pids)"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  # shellcheck disable=SC2086
  if kill -0 $pids 2>/dev/null; then
    kill -9 $pids 2>/dev/null || true
  fi
}

echo "==> mobile metro cleanup (cwd=$ROOT)"
for port in $PORTS; do
  kill_port "$port"
done

# Kill orphaned expo/metro node processes for this project (macOS/Linux).
if command -v pgrep >/dev/null 2>&1; then
  stale="$(pgrep -f "$ROOT.*(expo|metro)" 2>/dev/null || true)"
  if [ -n "$stale" ]; then
    echo "==> Stopping stale expo/metro for this project"
    # shellcheck disable=SC2086
    kill $stale 2>/dev/null || true
    sleep 1
  fi
fi

echo "OK metro cleanup"
