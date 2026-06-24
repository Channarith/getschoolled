#!/usr/bin/env bash
# Diagnose and fix QA/admin login on Vultr VKE (run where kubectl works).
set -euo pipefail

NS="${NAMESPACE:-aoep}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Salareen VKE login check (namespace=$NS) ==="

echo ""
echo "-- Pods --"
kubectl -n "$NS" get pods -l 'app in (identity,web,redis)' -o wide 2>/dev/null || {
  echo "kubectl failed — set KUBECONFIG to your VKE cluster." >&2
  exit 1
}

IDENTITY_POD="$(
  kubectl -n "$NS" get pods -l app=identity \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
)"
WEB_POD="$(
  kubectl -n "$NS" get pods -l app=web \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
)"

if [[ -z "$IDENTITY_POD" ]]; then
  echo "No Running identity pod." >&2
  exit 1
fi

echo ""
echo "-- Identity image / version (pod/$IDENTITY_POD) --"
kubectl -n "$NS" get pod "$IDENTITY_POD" -o jsonpath='  image={.spec.containers[0].image}{"\n"}'
kubectl -n "$NS" exec "$IDENTITY_POD" -- python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/version', timeout=5) as r:
        print('  version', json.loads(r.read().decode()))
except Exception as e:
    print('  version endpoint failed:', e)
" 2>/dev/null || true

echo ""
echo "-- Secret passwords (first 3 chars only) --"
for key in DEFAULT_ADMIN_PASSWORD QA_ACCOUNTS_PASSWORD; do
  val="$(kubectl -n "$NS" get secret aoep-secrets -o "jsonpath={.data.$key}" 2>/dev/null | base64 -d 2>/dev/null || true)"
  if [[ -z "$val" ]]; then
    echo "  $key: (missing — code defaults apply)"
  else
    echo "  $key: ${val:0:3}*** (${#val} chars)"
  fi
done

echo ""
echo "-- Direct identity login (in-cluster, same as web rewrite target) --"
kubectl -n "$NS" exec "$IDENTITY_POD" -- python3 - <<'PY'
import json
import urllib.error
import urllib.request

def try_login(email, password):
    req = urllib.request.Request(
        "http://127.0.0.1:8000/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            return resp.status, bool(body.get("token")), None
    except urllib.error.HTTPError as exc:
        return exc.code, False, exc.read().decode()[:200]
    except Exception as exc:
        return 0, False, str(exc)

cases = [
    ("admin@salareen.com", "88888888"),
    ("qa-pro@salareen.com", "QaTest123"),
    ("qa3", "QaTest123"),
]
for email, pw in cases:
    code, ok, err = try_login(email, pw)
    status = "OK" if ok else f"FAIL HTTP {code}"
    print(f"  {email}: {status}" + (f" ({err})" if err and not ok else ""))
PY

if [[ -n "$WEB_POD" ]]; then
  echo ""
  echo "-- Browser path: web pod -> identity (Next.js rewrite) --"
  kubectl -n "$NS" exec "$WEB_POD" -- node -e "
const http = require('http');
function post(body) {
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: 'identity', port: 8000, path: '/auth/login', method: 'POST',
      headers: {'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body)},
    }, (res) => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve({status: res.statusCode, body: d}));
    });
    req.on('error', reject);
    req.write(body); req.end();
  });
}
(async () => {
  const body = JSON.stringify({email: 'qa-pro@salareen.com', password: 'QaTest123'});
  const r = await post(body);
  const ok = r.status === 200 && r.body.includes('token');
  console.log('  web->identity qa-pro:', ok ? 'OK' : 'FAIL HTTP ' + r.status + ' ' + r.body.slice(0,120));
})().catch(e => console.error(e));
" 2>/dev/null || echo "  (web pod node check skipped)"
fi

echo ""
echo "-- Fix: reseed Redis + restart identity + verify --"
chmod +x "$ROOT/scripts/k8s_reseed_accounts.sh"
AUTO_RESTART=1 VERIFY_LOGIN=1 "$ROOT/scripts/k8s_reseed_accounts.sh"

echo ""
echo "If browser still 401, deploy fresh identity+web images (Deploy workflow), then re-run this script."
