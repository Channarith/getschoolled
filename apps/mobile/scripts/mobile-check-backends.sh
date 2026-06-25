#!/usr/bin/env bash
# Probe local AOEP backends used by the mobile app (curriculum :8005, identity :8008).
set -euo pipefail

check_port() {
  local name="$1" port="$2"
  if command -v nc >/dev/null 2>&1; then
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
      echo "  OK   $name listening on localhost:$port"
      return 0
    fi
  elif command -v curl >/dev/null 2>&1; then
    if curl -sf --connect-timeout 1 "http://127.0.0.1:${port}/" >/dev/null 2>&1 \
      || curl -sf --connect-timeout 1 "http://127.0.0.1:${port}/auth/me" >/dev/null 2>&1 \
      || curl -sf --connect-timeout 1 "http://127.0.0.1:${port}/docs" >/dev/null 2>&1; then
      echo "  OK   $name responding on localhost:$port"
      return 0
    fi
  fi
  echo "  WARN $name not reachable on localhost:$port"
  return 1
}

WARN=0
check_port "identity (login)" 8008 || WARN=$((WARN + 1))
check_port "curriculum (catalog)" 8005 || WARN=$((WARN + 1))

if [ "$WARN" -gt 0 ]; then
  echo
  echo "Start missing services from the repo root:"
  echo "  make run-identity                    # :8008 — Settings sign-in"
  echo "  ./scripts/run_local_service.sh curriculum   # :8005 — home catalog"
  exit 1
fi
exit 0
