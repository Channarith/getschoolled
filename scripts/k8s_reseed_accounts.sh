#!/usr/bin/env bash
# Force identity admin + QA personas into Redis on a running VKE/k8s cluster.
# On success, optionally restarts identity and verifies login in-cluster.
set -euo pipefail

NS="${NAMESPACE:-aoep}"
DEPLOY="${DEPLOYMENT:-identity}"
LABEL="${APP_LABEL:-app=$DEPLOY}"
REDIS_KEY="${REDIS_KEY:-aoep:identity:v1:state}"
AUTO_RESTART="${AUTO_RESTART:-1}"
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

_identity_pod() {
  kubectl -n "$NS" get pods -l "$LABEL" \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
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

_verify_login() {
  local pod="$1"
  echo "Verifying QA login inside pod/$pod ..."
  kubectl -n "$NS" exec "$pod" -- python3 - <<'PY'
import json
import os
import sys
import urllib.request

for candidate in ("/app/services/identity/src",):
    if os.path.isdir(candidate) and candidate not in sys.path:
        sys.path.insert(0, candidate)

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
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            results[label] = bool(body.get("token"))
    except Exception as exc:
        results[label] = False
        results[f"{label}_error"] = str(exc)
print(json.dumps(results))
ok = results.get("qa-pro@salareen.com") and results.get("qa3")
raise SystemExit(0 if ok else 1)
PY
}

echo "Looking for a running identity pod in namespace $NS ..."
POD="$(_identity_pod)"
if [[ -z "$POD" ]]; then
  echo "No Running pod with label $LABEL in namespace $NS." >&2
  kubectl -n "$NS" get pods -l "$LABEL" >&2 || true
  exit 1
fi

echo "Reseeding accounts via pod/$POD (pipe script to python3) ..."
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
LOGIN_OK="$(printf '%s' "$RESULT_JSON" | _json_field login_ok)"

if [[ "$PERSISTED" != "True" && "$PERSISTED" != "true" ]]; then
  echo "persisted=$PERSISTED — trying redis-cli fallback ..."
  _try_redis_cli_persist "$POD" || true
  PERSISTED="true"
fi

if [[ "$AUTO_RESTART" == "1" ]]; then
  echo "Restarting deployment/$DEPLOY so every replica reloads Redis ..."
  kubectl -n "$NS" rollout restart "deployment/$DEPLOY"
  kubectl -n "$NS" rollout status "deployment/$DEPLOY" --timeout=180s
  POD="$(_identity_pod)"
fi

if [[ "$VERIFY_LOGIN" == "1" && -n "$POD" ]]; then
  if ! _verify_login "$POD"; then
    echo ""
    echo "QA login still failing after reseed + restart." >&2
    echo "Check cluster secret password:" >&2
    echo "  kubectl -n $NS get secret aoep-secrets -o jsonpath='{.data.QA_ACCOUNTS_PASSWORD}' | base64 -d; echo" >&2
    echo "Expected: QaTest123 (unless you rotated it)." >&2
    exit 1
  fi
  echo "QA login verified OK on pod/$POD"
fi

echo ""
echo "Done. Try in browser: qa-pro@salareen.com / QaTest123 (or alias qa3)"
