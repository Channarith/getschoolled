#!/usr/bin/env bash
# synthetic_monitor.sh — probe salareen.com service health endpoints.
# Optional env: BASE_URL (default: https://salareen.com), TIMEOUT (default: 15)
# Exit 0 = all healthy. Exit 1 = one or more services degraded.
set -uo pipefail

BASE_URL="${BASE_URL:-https://salareen.com}"
TIMEOUT="${TIMEOUT:-15}"

PASS=0
FAIL=0

probe() {
  local name="$1" url="$2"
  local start_ms end_ms latency_ms status body sha
  start_ms=$(date +%s%3N)
  body=$(curl -sf --max-time "$TIMEOUT" "$url" 2>/dev/null || true)
  end_ms=$(date +%s%3N)
  latency_ms=$((end_ms - start_ms))

  if [ -z "$body" ]; then
    echo "  [$name] FAIL unreachable (${latency_ms}ms)"
    FAIL=$((FAIL + 1))
    return
  fi

  sha=$(echo "$body" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('git_sha') or d.get('sha') or '?')" 2>/dev/null || echo "?")
  echo "  [$name] OK sha=${sha} (${latency_ms}ms)"
  PASS=$((PASS + 1))
}

probe_health() {
  local name="$1" url="$2"
  local status
  status=$(curl -sfo /dev/null --max-time "$TIMEOUT" -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$status" = "200" ]; then
    echo "  [$name/health] OK (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  [$name/health] FAIL (HTTP $status)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Synthetic monitor: ${BASE_URL} ==="

# Web app root
probe_health "web" "${BASE_URL}/"

# Service /version probes via web proxy rewrites
for svc in orchestrator speech perception memory curriculum billing identity integrations; do
  probe "$svc" "${BASE_URL}/api/${svc}/version"
done

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
  echo "STATUS: DEGRADED — $FAIL service(s) unhealthy" >&2
  exit 1
fi

echo "STATUS: OK — all services healthy"
exit 0
