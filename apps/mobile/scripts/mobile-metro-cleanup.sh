#!/usr/bin/env bash
# Stop stale Metro/Expo dev servers (fixes port prompts, frozen starts, blank web).
#
# Default ports cover:
#   8081–8083  — Expo Go / native Metro
#   19000–19020 — Expo web / Metro web preview range (common agent/dev ports)
#
# Override: MOBILE_METRO_PORTS="8081 19040" bash scripts/mobile-metro-cleanup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Keep the list compact but broad enough that agent/web preview zombies die.
PORTS="${MOBILE_METRO_PORTS:-8081 8082 8083 19000 19001 19006 19007 19008 19009 19010 19011 19012 19020 19021 19030 19040}"

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
  for pid in $pids; do
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done
  # Confirm — some agent sandboxes cannot kill foreign PIDs.
  pids="$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "WARN port $port still listening (pid $pids) — kill from your own terminal:" >&2
    echo "     kill -9 $pids" >&2
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
    echo "==> Stopping stale expo/metro for this project (pid $stale)"
    # shellcheck disable=SC2086
    kill $stale 2>/dev/null || true
    sleep 1
    # shellcheck disable=SC2086
    for pid in $stale; do
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi
fi

echo "OK metro cleanup"
echo "    Start fresh: EXPO_OFFLINE=1 bash scripts/mobile-expo.sh start --port 8081"
echo "    Web:         EXPO_OFFLINE=1 bash scripts/mobile-expo.sh start --web --port 19020"
