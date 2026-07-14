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

if kubectl -n "$NS" get secret aoep-secrets >/dev/null 2>&1; then
  echo "aoep-secrets already exists in namespace '$NS' — leaving it untouched."
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
DEFAULT_ADMIN_PASSWORD="${DEFAULT_ADMIN_PASSWORD:-88888888}"
QA_ACCOUNTS_PASSWORD="${QA_ACCOUNTS_PASSWORD:-QaTest123}"

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
  --from-literal=DEFAULT_ADMIN_PASSWORD="$DEFAULT_ADMIN_PASSWORD" \
  --from-literal=QA_ACCOUNTS_PASSWORD="$QA_ACCOUNTS_PASSWORD"

echo "OK: aoep-secrets created. Future 'kubectl apply -k' runs will NOT modify it."
