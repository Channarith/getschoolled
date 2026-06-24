#!/usr/bin/env bash
# Force identity admin + QA personas into Redis on a running VKE/k8s cluster.
set -euo pipefail

NS="${NAMESPACE:-aoep}"
DEPLOY="${DEPLOYMENT:-identity}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/identity_reseed_redis.py"

if [[ ! -f "$SCRIPT" ]]; then
  echo "missing $SCRIPT" >&2
  exit 1
fi

echo "Reseeding accounts via deployment/$DEPLOY in namespace $NS ..."
kubectl -n "$NS" cp "$SCRIPT" "deploy/$DEPLOY:/tmp/identity_reseed_redis.py"
kubectl -n "$NS" exec "deploy/$DEPLOY" -- python3 /tmp/identity_reseed_redis.py
