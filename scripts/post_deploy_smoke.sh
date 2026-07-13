#!/usr/bin/env bash
# post_deploy_smoke.sh — verify all services report the same git_sha as the deployed tag.
# Required env: TAG (the git sha that was deployed)
# Optional env: NS (namespace, default: aoep), TIMEOUT (per-pod curl timeout, default: 30)
# Exit 0 = all services match. Exit 1 = mismatch or unreachable (triggers auto-rollback).
set -euo pipefail

NS="${NS:-aoep}"
TIMEOUT="${TIMEOUT:-30}"

if [ -z "${TAG:-}" ]; then
  echo "ERROR: TAG env var is required (the deployed git sha)" >&2
  exit 1
fi

# Service name -> internal port
declare -A PORTS
PORTS[orchestrator]=8000
PORTS[speech]=8002
PORTS[perception]=8003
PORTS[memory]=8004
PORTS[curriculum]=8005
PORTS[billing]=8006
PORTS[integrations]=8007
PORTS[identity]=8008
PORTS[web]=3000

PASS=0
FAIL=0
declare -A RESULTS

echo "=== SHA-match smoke: verifying tag=${TAG} in ns=${NS} ==="

for svc in orchestrator speech perception memory curriculum billing integrations identity web; do
  PORT="${PORTS[$svc]}"
  # Get first Running pod
  POD=$(kubectl -n "$NS" get pods -l "app=$svc" \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    2>/dev/null | head -n1 || true)

  if [ -z "$POD" ]; then
    echo "  [$svc] FAIL: no running pod found"
    RESULTS[$svc]="NO_POD"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Exec into pod and curl /version endpoint
  VERSION_JSON=$(kubectl -n "$NS" exec "$POD" -- \
    curl -sf --max-time "$TIMEOUT" "http://127.0.0.1:${PORT}/version" 2>/dev/null || true)

  if [ -z "$VERSION_JSON" ]; then
    echo "  [$svc] FAIL: /version unreachable on pod $POD"
    RESULTS[$svc]="UNREACHABLE"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Extract git_sha from JSON
  GIT_SHA=$(echo "$VERSION_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('git_sha') or d.get('sha') or '')" 2>/dev/null || true)

  if [ -z "$GIT_SHA" ]; then
    echo "  [$svc] FAIL: no git_sha in /version response: $VERSION_JSON"
    RESULTS[$svc]="NO_SHA"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Compare to expected TAG (match on prefix — TAG may be full sha, service may return short)
  if [[ "$TAG" == "$GIT_SHA"* ]] || [[ "$GIT_SHA" == "$TAG"* ]]; then
    echo "  [$svc] OK: sha=$GIT_SHA"
    RESULTS[$svc]="$GIT_SHA"
    PASS=$((PASS + 1))
  else
    echo "  [$svc] FAIL: sha=$GIT_SHA != expected=$TAG"
    RESULTS[$svc]="MISMATCH:$GIT_SHA"
    FAIL=$((FAIL + 1))
  fi
done

# Fleet uniformity check: all services must report the same sha
UNIQUE_SHAS=$(for svc in "${!RESULTS[@]}"; do echo "${RESULTS[$svc]}"; done | grep -v "^NO_POD\|^UNREACHABLE\|^NO_SHA\|^MISMATCH" | sort -u | wc -l)

echo ""
echo "=== Summary: $PASS passed, $FAIL failed, $UNIQUE_SHAS unique SHA(s) across fleet ==="

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL — $FAIL service(s) did not match expected SHA $TAG" >&2
  exit 1
fi

if [ "$UNIQUE_SHAS" -gt 1 ]; then
  echo "RESULT: FAIL — fleet non-uniform: $UNIQUE_SHAS different SHAs found" >&2
  exit 1
fi

echo "RESULT: OK — all services match $TAG"
exit 0
