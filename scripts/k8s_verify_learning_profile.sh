#!/usr/bin/env bash
# Verify learning-profile API is reachable on the public host (VKE / production).
# Usage: ./scripts/k8s_verify_learning_profile.sh [BASE_URL]
# Example: ./scripts/k8s_verify_learning_profile.sh http://45.63.91.80
set -euo pipefail

BASE="${1:-http://45.63.91.80}"
BASE="${BASE%/}"

echo "=== Learning profile API verify ($BASE) ==="

meta_code="$(curl -s -o /tmp/aoep_identity_meta.json -w '%{http_code}' "$BASE/identity/__meta" || true)"
echo "GET /identity/__meta -> HTTP $meta_code"
if [[ "$meta_code" != "200" ]]; then
  echo "FAIL: cannot reach identity __meta (routing or identity down)" >&2
  exit 1
fi

if ! grep -q 'learning-profile' /tmp/aoep_identity_meta.json; then
  echo "FAIL: identity __meta has no learning-profile routes (stale image)" >&2
  python3 -c "import json; m=json.load(open('/tmp/aoep_identity_meta.json')); print('version', m.get('version'), 'routes', m.get('route_count'))" 2>/dev/null || true
  exit 1
fi

ver="$(python3 -c "import json; print(json.load(open('/tmp/aoep_identity_meta.json')).get('version','?'))" 2>/dev/null || echo '?')"
echo "OK identity version=$ver exposes learning-profile routes"
echo "Next: deploy identity+web if stale, then signup and save survey once (onboarding_completed_at in cloud)."
