#!/usr/bin/env bash
# Probe backends used by the mobile app (cloud VKE or local Mac services).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"

read -r DEPLOY_MODE CLOUD_BASE <<< "$(node - <<'NODE'
const app = require("./app.json");
const mode = process.env.MOBILE_DEPLOY_MODE || app.expo.extra?.deployMode || "cloud";
const base = (process.env.MOBILE_CLOUD_BASE_URL || app.expo.extra?.cloudBaseUrl || "http://45.63.91.80").replace(/\/$/, "");
console.log(mode, base);
NODE
)"

check_http() {
  local name="$1" url="$2"
  if command -v curl >/dev/null 2>&1; then
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 "$url" || true)"
    if [[ "$code" == "200" || "$code" == "401" || "$code" == "404" ]]; then
      echo "  OK   $name responding ($url)"
      return 0
    fi
  fi
  echo "  WARN $name not reachable ($url)"
  return 1
}

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
if [ "$DEPLOY_MODE" = "cloud" ]; then
  echo "==> Backend mode: cloud ($CLOUD_BASE)"
  check_http "identity (login)" "$CLOUD_BASE/identity/__meta" || WARN=$((WARN + 1))
  check_http "curriculum (catalog)" "$CLOUD_BASE/curriculum/health" || WARN=$((WARN + 1))
  check_http "memory" "$CLOUD_BASE/memory/health" || WARN=$((WARN + 1))
  if [ "$WARN" -gt 0 ]; then
    echo
    echo "Cloud cluster may be down or unreachable from this network."
    echo "Override to local Mac services: MOBILE_DEPLOY_MODE=local npm run launch:android:native"
    exit 1
  fi
  exit 0
fi

echo "==> Backend mode: local (Mac services)"
check_port "identity (login)" 8008 || WARN=$((WARN + 1))
check_port "curriculum (catalog)" 8005 || WARN=$((WARN + 1))

if [ "$WARN" -gt 0 ]; then
  echo
  echo "Start missing services from the repo root:"
  echo "  make run-identity                    # :8008 — Settings sign-in"
  echo "  ./scripts/run_local_service.sh curriculum   # :8005 — home catalog"
  echo "Or use cloud: MOBILE_DEPLOY_MODE=cloud npm run launch:android:native"
  exit 1
fi
exit 0
