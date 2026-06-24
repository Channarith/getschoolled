#!/usr/bin/env bash
# Print identity / Redis / login diagnostics for VKE (run where kubectl works).
set -euo pipefail

NS="${NAMESPACE:-aoep}"

echo "=== Identity diagnostics (namespace=$NS) ==="

echo ""
echo "-- Pods --"
kubectl -n "$NS" get pods -l app=identity -o wide

echo ""
echo "-- Env (seed flags + redis) on first identity pod --"
POD="$(kubectl -n "$NS" get pods -l app=identity -o jsonpath='{.items[0].metadata.name}')"
kubectl -n "$NS" exec "$POD" -- env | grep -E '^(REDIS_URL|SEED_|DEFAULT_ADMIN|QA_ACCOUNTS|ADMIN_SECRET)=' | sort

echo ""
echo "-- Version --"
kubectl -n "$NS" exec "$POD" -- python3 -c "
import json, urllib.request
try:
    print(json.loads(urllib.request.urlopen('http://127.0.0.1:8000/version', timeout=5).read()))
except Exception as e:
    print('version failed:', e)
"

echo ""
echo "-- Redis snapshot (emails + id_by_email keys) --"
kubectl -n "$NS" exec redis-0 -- redis-cli GET aoep:identity:v1:state 2>/dev/null | python3 - <<'PY' || echo "(redis key missing or empty)"
import json, sys
raw = sys.stdin.read().strip()
if not raw or raw == "(nil)":
    print("Redis key aoep:identity:v1:state is EMPTY")
    raise SystemExit(0)
d = json.loads(raw)
print("account count:", len(d.get("accounts", {})))
for aid, acct in d.get("accounts", {}).items():
    print(" ", acct.get("email"), "admin=" + str(acct.get("is_admin", False)))
print("id_by_email:", sorted(d.get("id_by_email", {}).keys()))
PY

echo ""
echo "-- Fresh Python load from Redis (NOT the running uvicorn process) --"
kubectl -n "$NS" exec -i "$POD" -- python3 - <<'PY'
import json
import os
import sys

sys.path.insert(0, "/app/services/identity/src")
from identity.store import AccountStore
from identity.persistence import load_from_redis

store = AccountStore()
loaded = load_from_redis(store)
qa_pw = os.environ.get("QA_ACCOUNTS_PASSWORD", "QaTest123").strip() or "QaTest123"
admin_pw = os.environ.get("DEFAULT_ADMIN_PASSWORD", "88888888").strip() or "88888888"
print(json.dumps({
    "loaded_from_redis": loaded,
    "account_count": len(store._by_id),
    "id_by_email": sorted(store._id_by_email.keys()),
    "auth_admin": store.authenticate("admin@salareen.com", admin_pw) is not None,
    "auth_qa_pro": store.authenticate("qa-pro@salareen.com", qa_pw) is not None,
    "auth_qa3": store.authenticate("qa3", qa_pw) is not None,
}, indent=2))
PY

echo ""
echo "-- HTTP login on EACH pod (running uvicorn — what the browser hits) --"
ADMIN_SECRET="$(kubectl -n "$NS" get configmap aoep-config -o jsonpath='{.data.ADMIN_SECRET}')"
for p in $(kubectl -n "$NS" get pods -l app=identity -o jsonpath='{.items[*].metadata.name}'); do
  echo "pod $p:"
  kubectl -n "$NS" exec -i "$p" -- python3 - <<'PY'
import json, os, urllib.request, urllib.error

def post(email, password):
    req = urllib.request.Request(
        "http://127.0.0.1:8000/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode()).get("token") is not None
    except urllib.error.HTTPError as e:
        return e.code, False

qa = os.environ.get("QA_ACCOUNTS_PASSWORD", "QaTest123").strip() or "QaTest123"
admin = os.environ.get("DEFAULT_ADMIN_PASSWORD", "88888888").strip() or "88888888"
for label, em, pw in [
    ("admin", "admin@salareen.com", admin),
    ("qa-pro", "qa-pro@salareen.com", qa),
    ("qa3", "qa3", qa),
]:
    code, ok = post(em, pw)
    print(f"  {label}: {'OK' if ok else 'FAIL HTTP '+str(code)}")
PY
done

echo ""
echo "-- Ops reseed (updates LIVE uvicorn memory) --"
echo "ADMIN_SECRET=${ADMIN_SECRET}"
for p in $(kubectl -n "$NS" get pods -l app=identity -o jsonpath='{.items[*].metadata.name}'); do
  echo "pod $p ops-reseed:"
  kubectl -n "$NS" exec -i "$p" -- env "ADMIN_SECRET=${ADMIN_SECRET}" python3 - <<'PY' || true
import json
import os
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
        print(resp.status, resp.read().decode())
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}: {exc.read().decode()[:400]}")
except Exception as exc:
    print(f"ERROR: {exc}")
PY
done

echo ""
echo "If ops-reseed returns 404 → deploy a new identity image (GitHub Deploy workflow)."
echo "If Redis auth works but HTTP FAIL → run: ./scripts/k8s_reseed_accounts.sh (with ops-reseed step)"
