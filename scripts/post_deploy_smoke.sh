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
# Two verification modes:
#   * DIGEST mode (preferred): set DIGEST_DIR=<dir> containing <svc>.digest files
#     (one immutable sha256 digest per service, as produced by deploy.yml). Each
#     Deployment must run an image pinned to EXACTLY that digest
#     (registry/svc@sha256:...). This is the "promote the exact artifact" gate —
#     see docs/vv-master-plan.txt section 4.
#   * TAG mode (legacy/manual): set TAG=<git-sha>. Each Deployment must run
#     registry/svc:<TAG>. Kept for deploy-gate.yml and partial manual deploys.
#
# Required env: DIGEST_DIR *or* TAG.
# Optional env: NS (namespace, default: aoep)
# Exit 0 = all services on the expected artifact and available. Exit 1 =
# mismatch/unavailable (triggers auto-rollback).
set -euo pipefail

NS="${NS:-aoep}"

MODE=""
if [ -n "${DIGEST_DIR:-}" ]; then
  MODE="digest"
elif [ -n "${TAG:-}" ]; then
  MODE="tag"
else
  echo "ERROR: set DIGEST_DIR (preferred) or TAG (legacy) — neither is set" >&2
  exit 1
fi

# Deployments to check. When SERVICES env var is set (space-separated list from
# the workflow), only check those services — avoids false failures when a partial
# deploy (e.g. "identity + web only") leaves other services on :latest tags.
if [ -n "${SERVICES:-}" ]; then
  read -ra SERVICES <<< "$SERVICES"
else
  SERVICES=(orchestrator speech perception memory curriculum billing integrations identity harvester web)
fi

PASS=0
FAIL=0

if [ "$MODE" = "digest" ]; then
  echo "=== digest smoke: verifying built digests (DIGEST_DIR=${DIGEST_DIR}) in ns=${NS} ==="
else
  echo "=== image-tag smoke: verifying tag=${TAG} in ns=${NS} ==="
fi

for svc in "${SERVICES[@]}"; do
  # The image the Deployment's pod template is set to.
  IMG=$(kubectl -n "$NS" get deployment "$svc" \
    -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)

  if [ -z "$IMG" ]; then
    echo "  [$svc] FAIL: deployment not found"
    FAIL=$((FAIL + 1))
    continue
  fi

  if [ "$MODE" = "digest" ]; then
    # Expected immutable digest for this service (sha256:...).
    digest_file="${DIGEST_DIR}/${svc}.digest"
    if [ ! -f "$digest_file" ]; then
      echo "  [$svc] FAIL: no digest file $digest_file"
      FAIL=$((FAIL + 1))
      continue
    fi
    EXPECTED="$(tr -d '[:space:]' < "$digest_file")"
    # A digest-pinned image is registry/svc@sha256:... — the ref after '@'.
    case "$IMG" in
      *@*) DEPLOYED="${IMG#*@}" ;;
      *)   echo "  [$svc] FAIL: image is not digest-pinned ($IMG)"
           FAIL=$((FAIL + 1)); continue ;;
    esac
    if [ "$DEPLOYED" != "$EXPECTED" ]; then
      echo "  [$svc] FAIL: digest=$DEPLOYED != expected=$EXPECTED ($IMG)"
      FAIL=$((FAIL + 1))
      continue
    fi
  else
    # Everything after the last ':' is the tag (registry host may itself contain
    # a ':port', so only split on the final colon).
    IMG_TAG="${IMG##*:}"
    if [ "$IMG_TAG" != "$TAG" ]; then
      echo "  [$svc] FAIL: image tag=$IMG_TAG != expected=$TAG ($IMG)"
      FAIL=$((FAIL + 1))
      continue
    fi
  fi

  # Confirm the rollout is complete: updated/available replicas meet the spec.
  DESIRED=$(kubectl -n "$NS" get deployment "$svc" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "")
  AVAILABLE=$(kubectl -n "$NS" get deployment "$svc" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  AVAILABLE="${AVAILABLE:-0}"

  if [ -n "$DESIRED" ] && [ "$AVAILABLE" -lt "$DESIRED" ]; then
    echo "  [$svc] FAIL: only $AVAILABLE/$DESIRED replicas available"
    FAIL=$((FAIL + 1))
    continue
  fi

  echo "  [$svc] OK: $IMG (${AVAILABLE:-?}/${DESIRED:-?} available)"
  PASS=$((PASS + 1))
done

EXPECTED_DESC="$([ "$MODE" = "digest" ] && echo "built digests" || echo "tag=$TAG")"
echo ""
echo "=== Summary: $PASS passed, $FAIL failed ($EXPECTED_DESC) ==="

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL — $FAIL service(s) not on $EXPECTED_DESC" >&2
  exit 1
fi

echo "RESULT: OK — all services on $EXPECTED_DESC"
exit 0
