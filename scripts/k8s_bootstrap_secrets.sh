#!/usr/bin/env bash
# One-time bootstrap of the `aoep-secrets` Secret in the VKE cluster.
#
# WHY: aoep-secrets is intentionally NOT part of the applied kustomization (see
# infra/k8s/aoep-secrets.example.yaml), so `kubectl apply -k` can never reset real
# secret values to "__INJECT__". This creates the Secret once from env vars.
#
# SAFE BY DESIGN: if the Secret already exists it does NOTHING (so re-running a
# deploy never clobbers your live secrets). To change a single value later, use:
#   kubectl -n aoep patch secret aoep-secrets --type merge \
#     -p "{\"stringData\":{\"LIVEKIT_API_SECRET\":\"$LIVEKIT_API_SECRET\"}}"
#
# Usage (export the values you have; LiveKit is required):
#   export LIVEKIT_API_KEY=...  LIVEKIT_API_SECRET=...
#   bash scripts/k8s_bootstrap_secrets.sh
set -euo pipefail

NS="${AOEP_NAMESPACE:-aoep}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl not found / not configured for the cluster." >&2
  exit 1
fi

ensure_redis_password() {
  # Redis --requirepass reads aoep-secrets key redis-password. Identity and the
  # other backends read REDIS_PASSWORD. Fill whichever is missing, copying the
  # one that already exists. Never replace a value that is already set.
  python3 - "$NS" <<'PY'
import base64, json, secrets, subprocess, sys
ns = sys.argv[1]
raw = subprocess.check_output(
    ["kubectl", "-n", ns, "get", "secret", "aoep-secrets", "-o", "json"],
    text=True,
)
data = json.loads(raw).get("data") or {}
def dec(key):
    blob = data.get(key) or ""
    if not blob:
        return ""
    return base64.b64decode(blob).decode("utf-8", "replace")
existing = dec("redis-password") or dec("REDIS_PASSWORD")
password = existing or secrets.token_hex(24)
missing = {}
if not dec("redis-password"):
    missing["redis-password"] = password
if not dec("REDIS_PASSWORD"):
    missing["REDIS_PASSWORD"] = password
if not missing:
    print("redis password already set on aoep-secrets")
    raise SystemExit(0)
patch = json.dumps({"stringData": missing})
subprocess.check_call(
    ["kubectl", "-n", ns, "patch", "secret", "aoep-secrets", "--type", "merge", "-p", patch]
)
print("filled missing redis password keys:", ", ".join(sorted(missing)))
PY
}

if kubectl -n "$NS" get secret aoep-secrets >/dev/null 2>&1; then
  echo "aoep-secrets already exists in namespace '$NS' — leaving existing values untouched."
  ensure_redis_password
  echo "To change one value: kubectl -n $NS patch secret aoep-secrets --type merge -p '{\"stringData\":{\"KEY\":\"VALUE\"}}'"
  exit 0
fi

: "${LIVEKIT_API_KEY:?export LIVEKIT_API_KEY (from LiveKit Cloud) before running}"
: "${LIVEKIT_API_SECRET:?export LIVEKIT_API_SECRET (from LiveKit Cloud) before running}"

# Optional values default to empty/demo; override by exporting them.
DATABASE_URL="${DATABASE_URL:-}"
PAYMENT_API_KEY="${PAYMENT_API_KEY:-}"
OBJECT_STORE_ACCESS_KEY="${OBJECT_STORE_ACCESS_KEY:-}"
OBJECT_STORE_SECRET_KEY="${OBJECT_STORE_SECRET_KEY:-}"
NEMOTRON_API_KEY="${NEMOTRON_API_KEY:-}"
LLM_API_KEY="${LLM_API_KEY:-}"
ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}"
XAI_API_KEY="${XAI_API_KEY:-}"
GEMINI_API_KEY="${GEMINI_API_KEY:-}"
BUG_REPORT_GITHUB_TOKEN="${BUG_REPORT_GITHUB_TOKEN:-}"
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-88888888}"
QA_ACCOUNTS_PASSWORD="${QA_ACCOUNTS_PASSWORD:-QaTest123}"
REDIS_PASSWORD="${REDIS_PASSWORD:-$(python3 -c 'import secrets; print(secrets.token_hex(24))')}"

echo "Creating aoep-secrets in namespace '$NS'…"
kubectl -n "$NS" create secret generic aoep-secrets \
  --from-literal=LIVEKIT_API_KEY="$LIVEKIT_API_KEY" \
  --from-literal=LIVEKIT_API_SECRET="$LIVEKIT_API_SECRET" \
  --from-literal=DATABASE_URL="$DATABASE_URL" \
  --from-literal=PAYMENT_API_KEY="$PAYMENT_API_KEY" \
  --from-literal=OBJECT_STORE_ACCESS_KEY="$OBJECT_STORE_ACCESS_KEY" \
  --from-literal=OBJECT_STORE_SECRET_KEY="$OBJECT_STORE_SECRET_KEY" \
  --from-literal=NEMOTRON_API_KEY="$NEMOTRON_API_KEY" \
  --from-literal=LLM_API_KEY="$LLM_API_KEY" \
  --from-literal=ELEVENLABS_API_KEY="$ELEVENLABS_API_KEY" \
  --from-literal=XAI_API_KEY="$XAI_API_KEY" \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --from-literal=BUG_REPORT_GITHUB_TOKEN="$BUG_REPORT_GITHUB_TOKEN" \
  --from-literal=DEFAULT_ADMIN_PASSWORD="$DEFAULT_ADMIN_PASSWORD" \
  --from-literal=QA_ACCOUNTS_PASSWORD="$QA_ACCOUNTS_PASSWORD" \
  --from-literal=redis-password="$REDIS_PASSWORD" \
  --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD"

echo "OK: aoep-secrets created. Future 'kubectl apply -k' runs will NOT modify it."
