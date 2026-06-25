#!/usr/bin/env bash
# Verify /jobs serves the Careers HTML page (not raw curriculum JSON).
#
# Usage:
#   BASE_URL=http://45.63.91.80 bash scripts/k8s_verify_jobs_page.sh
#   BASE_URL=https://www.salareen.com bash scripts/k8s_verify_jobs_page.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://45.63.91.80}"
BASE_URL="${BASE_URL%/}"

echo "==> Careers page: ${BASE_URL}/jobs"
BODY="$(curl -fsS --max-time 20 "${BASE_URL}/jobs" || true)"
if [[ -z "$BODY" ]]; then
  echo "FAIL: empty response from ${BASE_URL}/jobs" >&2
  exit 1
fi

if echo "$BODY" | head -c 200 | grep -q '"jobs"[[:space:]]*:[[:space:]]*\['; then
  echo "FAIL: /jobs returned curriculum JSON (ingress routes to curriculum, not web)." >&2
  echo "  Fix: kubectl apply -k infra/k8s-vke && ensure /jobs -> web service." >&2
  echo "  Preview: $(echo "$BODY" | head -c 120)…" >&2
  exit 1
fi

if ! echo "$BODY" | grep -qiE '<html|Careers|__next'; then
  echo "FAIL: /jobs did not look like the Next.js Careers page." >&2
  echo "  Preview: $(echo "$BODY" | head -c 200)…" >&2
  exit 1
fi

echo "OK /jobs returns HTML (Careers page)"

echo "==> Jobs API: ${BASE_URL}/curriculum/jobs"
API="$(curl -fsS --max-time 20 "${BASE_URL}/curriculum/jobs?limit=3" || true)"
if echo "$API" | grep -q '"jobs"'; then
  echo "OK /curriculum/jobs returns JSON job list"
else
  echo "WARN: /curriculum/jobs did not return expected JSON (check aoep-apis ingress)" >&2
fi
