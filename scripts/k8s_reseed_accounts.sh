#!/usr/bin/env bash
# Force identity admin + QA personas into Redis AND live identity pods.
# The piped Python script writes Redis but runs in a separate process — it does
# NOT update the running uvicorn workers. We therefore ops-reseed every pod
# (POST /admin/ops/reseed-seeded) and verify HTTP login on each replica.
set -euo pipefail

NS="${NAMESPACE:-aoep}"
DEPLOY="${DEPLOYMENT:-identity}"
LABEL="${APP_LABEL:-app=$DEPLOY}"
REDIS_KEY="${REDIS_KEY:-aoep:identity:v1:state}"
AUTO_RESTART="${AUTO_RESTART:-0}"
VERIFY_LOGIN="${VERIFY_LOGIN:-1}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/identity_reseed_redis.py"

if [[ ! -f "$SCRIPT" ]]; then
  echo "missing $SCRIPT" >&2
  exit 1
fi

_json_field() {
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('$1', ''))"
}

_admin_secret() {
  kubectl -n "$NS" get configmap aoep-config -o jsonpath='{.data.ADMIN_SECRET}' 2>/dev/null \
    || echo "dev-admin-secret"
}

_identity_pods() {
  kubectl -n "$NS" get pods -l "$LABEL" \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}'
}

_identity_pod() {
  _identity_pods | head -n1
}

_redis_pod() {
  kubectl -n "$NS" get pods -l app=redis \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
}

_try_redis_cli_persist() {
  local pod="$1"
  local redis_pod
  redis_pod="$(_redis_pod)"
  if [[ -z "$redis_pod" ]]; then
    echo "No Running redis pod for fallback persist." >&2
    return 1
  fi
  echo "Fallback: writing Redis key via pod/$redis_pod (redis-cli) ..."
  local payload
  payload="$(
    kubectl -n "$NS" exec -i "$pod" -- env DUMP_REDIS_JSON=1 python3 - < "$SCRIPT" \
      | sed -n '/^REDIS_JSON=/s/^REDIS_JSON=//p' | head -n1
  )"
  if [[ -z "$payload" ]]; then
    echo "Could not build Redis payload from identity pod." >&2
    return 1
  fi
  printf '%s' "$payload" | kubectl -n "$NS" exec -i "$redis_pod" -- \
    redis-cli -n 0 -x SET "$REDIS_KEY" >/dev/null
  echo "redis-cli SET ok on $redis_pod"
}

_ops_reseed_pod() {
  local pod="$1"
  local secret="$2"
  echo "Ops reseed on pod/$pod (live uvicorn memory) ..."
  kubectl -n "$NS" exec "$pod" -- env "ADMIN_SECRET=$secret" python3 - <<'PY'
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
        body = json.loads(resp.read().decode())
        print(json.dumps(body))
        if resp.status != 200 or not body.get("reseeded"):
            raise SystemExit(1)
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}: {exc.read().decode()[:300]}", file=sys.stderr)
    raise SystemExit(1)
PY
}

_ops_reseed_all() {
  local secret="$1"
  local pod
  while IFS= read -r pod; do
    [[ -z "$pod" ]] && continue
    _ops_reseed_pod "$pod" "$secret"
  done < <(_identity_pods)
}

_verify_all_pods() {
  local pod failed=0
  while IFS= read -r pod; do
    [[ -z "$pod" ]] && continue
    echo "HTTP login verify on pod/$pod ..."
    if ! POD_NAME="$pod" kubectl -n "$NS" exec "$pod" -- env POD_NAME="$pod" python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

qa_pw = os.environ.get("QA_ACCOUNTS_PASSWORD", "QaTest123").strip() or "QaTest123"
checks = {
    "qa-pro@salareen.com": ("qa-pro@salareen.com", qa_pw),
    "qa3": ("qa3", qa_pw),
}
results = {}
for label, (email, pw) in checks.items():
    req = urllib.request.Request(
        "http://127.0.0.1:8000/auth/login",
        data=json.dumps({"email": email, "password": pw}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            results[label] = bool(body.get("token"))
    except urllib.error.HTTPError as exc:
        results[label] = False
        results[f"{label}_error"] = f"HTTP {exc.code}: {exc.read().decode()[:120]}"
    except Exception as exc:
        results[label] = False
        results[f"{label}_error"] = str(exc)
print(json.dumps(results))
ok = results.get("qa-pro@salareen.com") and results.get("qa3")
raise SystemExit(0 if ok else 1)
PY
    then
      echo "  OK on $pod"
    else
      echo "  FAIL on $pod" >&2
      failed=1
    fi
  done < <(_identity_pods)
  return "$failed"
}

echo "Looking for running identity pods in namespace $NS ..."
POD="$(_identity_pod)"
if [[ -z "$POD" ]]; then
  echo "No Running pod with label $LABEL in namespace $NS." >&2
  kubectl -n "$NS" get pods -l "$LABEL" >&2 || true
  exit 1
fi

echo "Step 1/3: write Redis snapshot via pod/$POD (separate Python process) ..."
set +e
OUTPUT="$(kubectl -n "$NS" exec -i "$POD" -- python3 - < "$SCRIPT" 2>&1 | tee /dev/stderr)"
RESEED_RC=$?
set -e
RESULT_JSON="$(printf '%s\n' "$OUTPUT" | sed -n '/^RESULT_JSON=/s/^RESULT_JSON=//p' | tail -n1)"
if [[ -z "$RESULT_JSON" ]]; then
  echo "Reseed script did not emit RESULT_JSON (exit $RESEED_RC)." >&2
  exit 1
fi

PERSISTED="$(printf '%s' "$RESULT_JSON" | _json_field persisted)"
if [[ "$PERSISTED" != "True" && "$PERSISTED" != "true" ]]; then
  echo "persisted=$PERSISTED — trying redis-cli fallback ..."
  _try_redis_cli_persist "$POD" || true
fi

SECRET="$(_admin_secret)"
echo ""
echo "Step 2/3: ops-reseed EVERY running identity pod (updates live uvicorn memory) ..."
if ! _ops_reseed_all "$SECRET"; then
  echo ""
  echo "Ops reseed failed (404 = identity image too old; need Deploy workflow)." >&2
  echo "Trying rollout restart as fallback ..." >&2
  kubectl -n "$NS" rollout restart "deployment/$DEPLOY"
  kubectl -n "$NS" rollout status "deployment/$DEPLOY" --timeout=180s
  _ops_reseed_all "$SECRET" || true
fi

if [[ "$AUTO_RESTART" == "1" ]]; then
  echo ""
  echo "Optional restart deployment/$DEPLOY ..."
  kubectl -n "$NS" rollout restart "deployment/$DEPLOY"
  kubectl -n "$NS" rollout status "deployment/$DEPLOY" --timeout=180s
fi

echo ""
echo "Step 3/3: verify HTTP login on every identity replica ..."
if [[ "$VERIFY_LOGIN" == "1" ]]; then
  if ! _verify_all_pods; then
    echo ""
    echo "HTTP login still failing on one or more pods." >&2
    echo "Check: kubectl -n $NS logs -l app=identity --tail=50" >&2
    exit 1
  fi
fi

echo ""
echo "Done. Browser login should work now:"
echo "  qa-pro@salareen.com / QaTest123  (or username qa3)"
