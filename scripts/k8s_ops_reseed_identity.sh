#!/usr/bin/env bash
# Ops-reseed every identity pod via python3 (identity images have no curl).
set -euo pipefail

NS="${NAMESPACE:-aoep}"
ADMIN_SECRET="${ADMIN_SECRET:-$(kubectl -n "$NS" get configmap aoep-config -o jsonpath='{.data.ADMIN_SECRET}' 2>/dev/null || echo dev-admin-secret)}"

for p in $(kubectl -n "$NS" get pods -l app=identity -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== ops reseed $p ==="
  kubectl -n "$NS" exec "$p" -- env "ADMIN_SECRET=${ADMIN_SECRET}" python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

secret = os.environ.get("ADMIN_SECRET", "dev-admin-secret")
req = urllib.request.Request(
    "http://127.0.0.1:8000/admin/ops/reseed-seeded",
    data=b"",
    headers={"X-Admin-Secret": secret},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode()
        print(body)
        data = json.loads(body)
        if not data.get("reseeded") or not data.get("login_ok", {}).get("qa-pro@salareen.com"):
            sys.exit(1)
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}: {exc.read().decode()[:500]}", file=sys.stderr)
    sys.exit(1)
PY
  echo ""
done

echo "Done. Test login: qa-pro@salareen.com / QaTest123"
