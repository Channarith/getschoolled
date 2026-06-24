#!/usr/bin/env bash
# Force identity admin + QA personas into Redis on a running VKE/k8s cluster.
set -euo pipefail

NS="${NAMESPACE:-aoep}"
DEPLOY="${DEPLOYMENT:-identity}"
LABEL="${APP_LABEL:-app=$DEPLOY}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/identity_reseed_redis.py"

if [[ ! -f "$SCRIPT" ]]; then
  echo "missing $SCRIPT" >&2
  exit 1
fi

echo "Looking for a running identity pod in namespace $NS ..."
POD="$(
  kubectl -n "$NS" get pods -l "$LABEL" -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
)"
if [[ -z "$POD" ]]; then
  echo "No Running pod with label $LABEL in namespace $NS." >&2
  kubectl -n "$NS" get pods -l "$LABEL" >&2 || true
  exit 1
fi

echo "Reseeding accounts via pod/$POD ..."
kubectl -n "$NS" cp "$SCRIPT" "$POD:/tmp/identity_reseed_redis.py"
kubectl -n "$NS" exec "$POD" -- python3 /tmp/identity_reseed_redis.py
