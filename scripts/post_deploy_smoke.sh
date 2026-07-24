#!/usr/bin/env bash
# post_deploy_smoke.sh — verify every deployment is actually running the image
# tag we just deployed (and that the rollout is complete/available).
#
# Why image-tag verification instead of curl-ing /version:
#   * The service containers are slim (no curl/wget), so `kubectl exec -- curl`
#     always failed → the old gate reported every service "unreachable" and
#     auto-rolled-back HEALTHY deploys, which is why the cluster kept running old
#     images.
#   * git_sha in /version comes from AOEP_GIT_SHA, which the image build does not
#     stamp, so a SHA compare could never pass either.
#   * The deploy step already ran `kubectl rollout status` (readiness probes must
#     pass), so the app is proven to serve. All that remains to verify is that the
#     Deployment's pod template references the tag we intended — that is exactly
#     what set-image + a completed rollout guarantees, and it needs nothing inside
#     the container.
#
# Required env: TAG (the image tag / git sha that was deployed)
# Optional env: NS (namespace, default: aoep)
# Exit 0 = all services on TAG and available. Exit 1 = mismatch/unavailable
# (triggers auto-rollback).
set -euo pipefail

NS="${NS:-aoep}"

if [ -z "${TAG:-}" ]; then
  echo "ERROR: TAG env var is required (the deployed image tag)" >&2
  exit 1
fi

# Deployments to check. When SERVICES env var is set (space-separated list from
# the workflow), only check those services — avoids false failures when a partial
# deploy (e.g. "identity + web only") leaves other services on :latest tags.
if [ -n "${SERVICES:-}" ]; then
  read -ra SERVICES <<< "$SERVICES"
else
  SERVICES=(orchestrator speech perception memory curriculum billing integrations identity web)
fi

PASS=0
FAIL=0

echo "=== image-tag smoke: verifying tag=${TAG} in ns=${NS} ==="

for svc in "${SERVICES[@]}"; do
  # The image the Deployment's pod template is set to.
  IMG=$(kubectl -n "$NS" get deployment "$svc" \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)

  if [ -z "$IMG" ]; then
    echo "  [$svc] FAIL: deployment not found"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Everything after the last ':' is the tag (registry host may itself contain a
  # ':port', so only split on the final colon).
  IMG_TAG="${IMG##*:}"

  if [ "$IMG_TAG" != "$TAG" ]; then
    echo "  [$svc] FAIL: image tag=$IMG_TAG != expected=$TAG ($IMG)"
    FAIL=$((FAIL + 1))
    continue
  fi

  # Confirm the rollout is complete: updated/available replicas meet the spec.
  DESIRED=$(kubectl -n "$NS" get deployment "$svc" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "")
  AVAILABLE=$(kubectl -n "$NS" get deployment "$svc" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  AVAILABLE="${AVAILABLE:-0}"

  if [ -n "$DESIRED" ] && [ "$AVAILABLE" -lt "$DESIRED" ]; then
    echo "  [$svc] FAIL: only $AVAILABLE/$DESIRED replicas available on $TAG"
    FAIL=$((FAIL + 1))
    continue
  fi

  echo "  [$svc] OK: $IMG (${AVAILABLE:-?}/${DESIRED:-?} available)"
  PASS=$((PASS + 1))
done

echo ""
echo "=== Summary: $PASS passed, $FAIL failed (tag=$TAG) ==="

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL — $FAIL service(s) not on tag $TAG" >&2
  exit 1
fi

echo "RESULT: OK — all services on $TAG"
exit 0
