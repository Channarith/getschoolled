#!/usr/bin/env bash
# manual_deploy_pr661.sh — one-shot local deploy of PR #661 to salareen.com
# when GitHub Actions is unavailable (private account, billing blocked, etc.).
#
# What this PR actually changes on the cluster
# --------------------------------------------
#   * services/identity      — new PersistenceConflict retry middleware + 409
#                              header stamp. REQUIRES a rebuilt identity image.
#   * apps/web               — version-only change (apps/web/app/lib/version.ts
#                              + apps/web/package.json). Rebuild so the UI
#                              footer / /version endpoint show v0.66.0.
#   * apps/mobile            — mobile-only (MascotActor, AuthScreen contrast,
#                              FirstSignInAssistant walker/age-morph). Not in
#                              the cluster — ships via EAS / Expo OTA. NOT
#                              handled by this script.
#
# The other 12 services the full Deploy workflow builds (orchestrator, speech,
# perception, memory, curriculum, billing, integrations, harvester,
# course-studio, children-lab, audio-lab, music) are unchanged by this PR and
# are intentionally LEFT ALONE. Rebuilding them from source would push floating
# tags over whatever digests are serving today — exactly the "digest pin wiped
# by a mutable tag" footgun that deploy-vke-manual.yml goes to such lengths to
# avoid.
#
# Mirrors .github/workflows/deploy-vke-manual.yml step-for-step so running this
# locally matches what a healthy CI run would have done.
#
# Prerequisites
# -------------
#   * docker + buildx on your machine (buildx is bundled with Docker Desktop).
#   * kubectl pointed at the VKE cluster (export KUBECONFIG=...). The RUNBOOK
#     at infra/k8s-vke/RUNBOOK.txt covers how to fetch kubeconfig-vke.yaml
#     from vultr-cli.
#   * Vultr Container Registry credentials in VULTR_REGISTRY_USERNAME /
#     VULTR_REGISTRY_PASSWORD (same values the GitHub Actions secrets hold).
#   * Running from a clean checkout at the commit you want to ship.
#     The script refuses to run with uncommitted changes to avoid surprising
#     "what source did we actually build" questions after the fact.
#
# Usage
# -----
#   export VULTR_REGISTRY_USERNAME=...
#   export VULTR_REGISTRY_PASSWORD=...
#   export KUBECONFIG=~/kubeconfig-vke.yaml
#   ./scripts/manual_deploy_pr661.sh                     # deploy identity + web
#   SERVICES="identity"       ./scripts/manual_deploy_pr661.sh   # identity only
#   SERVICES="identity web"   ./scripts/manual_deploy_pr661.sh   # explicit
#   DRY_RUN=1 ./scripts/manual_deploy_pr661.sh           # print, don't push
#
# On smoke-check failure the script rolls back the services it touched.

set -euo pipefail

REGISTRY="${REGISTRY:-sjc.vultrcr.com/salareen}"
NAMESPACE="${NAMESPACE:-aoep}"
SERVICES="${SERVICES:-identity web}"
DRY_RUN="${DRY_RUN:-0}"
# When unset, use the branch's HEAD SHA so the pushed tag matches `git rev-parse`.
TAG="${TAG:-$(git rev-parse --short=40 HEAD)}"

cd "$(git rev-parse --show-toplevel)"

echo "============================================================"
echo "AOEP / salareen.com manual deploy (PR #661 scope)"
echo "  registry : ${REGISTRY}"
echo "  namespace: ${NAMESPACE}"
echo "  services : ${SERVICES}"
echo "  tag      : ${TAG}"
echo "  dry run  : ${DRY_RUN}"
echo "============================================================"

# -- Preflight ----------------------------------------------------------------
if [ "${DRY_RUN}" != "1" ]; then
  if [ -z "${VULTR_REGISTRY_USERNAME:-}" ] || [ -z "${VULTR_REGISTRY_PASSWORD:-}" ]; then
    echo "ERROR: set VULTR_REGISTRY_USERNAME and VULTR_REGISTRY_PASSWORD (same values as the GH Actions secrets)." >&2
    exit 2
  fi
  if ! command -v docker >/dev/null; then
    echo "ERROR: docker not on PATH" >&2
    exit 2
  fi
  if ! command -v kubectl >/dev/null; then
    echo "ERROR: kubectl not on PATH" >&2
    exit 2
  fi
  if ! kubectl -n "${NAMESPACE}" get deploy identity >/dev/null 2>&1; then
    echo "ERROR: deployment/identity not found in ns=${NAMESPACE}. Is KUBECONFIG pointed at the right cluster?" >&2
    exit 2
  fi
fi

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "ERROR: working tree is dirty. Commit or stash first so the deploy image matches the pushed commit." >&2
  echo "       (git status to see what is dirty)" >&2
  exit 2
fi

# Map service name -> Dockerfile. Mirrors deploy-vke-manual.yml setup-matrix.
dockerfile_for() {
  case "$1" in
    identity) echo "services/identity/Dockerfile" ;;
    web)      echo "apps/web/Dockerfile" ;;
    memory)   echo "services/memory/Dockerfile" ;;
    *)
      echo "ERROR: unknown service '$1' - this script only handles identity, web, memory." >&2
      exit 3
      ;;
  esac
}

DIGEST_DIR="$(mktemp -d -t aoep-digests-XXXXXX)"
echo "digests -> ${DIGEST_DIR}"

# -- Registry login -----------------------------------------------------------
if [ "${DRY_RUN}" = "1" ]; then
  echo "[dry] docker login ${REGISTRY}"
else
  echo "${VULTR_REGISTRY_PASSWORD}" | \
    docker login "${REGISTRY}" -u "${VULTR_REGISTRY_USERNAME}" --password-stdin
fi

# -- Build + push each service, capture digest --------------------------------
# `buildx build --push --metadata-file` writes containerimage.digest (sha256) so
# we can pin the exact artifact that was pushed. This is the same invariant as
# docs/vv-master-plan.txt §4 that the Deploy workflows rely on.
for svc in ${SERVICES}; do
  dockerfile="$(dockerfile_for "${svc}")"
  image_tag="${REGISTRY}/${svc}:${TAG}"
  metadata="${DIGEST_DIR}/${svc}.meta.json"
  digest_out="${DIGEST_DIR}/${svc}.digest"

  echo "------------------------------------------------------------"
  echo "building ${svc} (${dockerfile} -> ${image_tag})"

  if [ "${DRY_RUN}" = "1" ]; then
    echo "[dry] docker buildx build --push --file ${dockerfile} --tag ${image_tag} --metadata-file ${metadata} ."
    # Give downstream steps a deterministic placeholder so --dry-run exercises
    # the whole pipeline.
    echo "sha256:dryrun0000000000000000000000000000000000000000000000000000000000" > "${digest_out}"
    continue
  fi

  docker buildx build \
    --push \
    --file "${dockerfile}" \
    --tag "${image_tag}" \
    --metadata-file "${metadata}" \
    .

  # metadata JSON has a key called "containerimage.digest" whose value is the
  # sha256 digest of the just-pushed image.
  digest="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['containerimage.digest'])" "${metadata}")"
  if [ -z "${digest}" ]; then
    echo "ERROR: no digest extracted from ${metadata}" >&2
    exit 4
  fi
  echo "${digest}" > "${digest_out}"
  echo "${svc} -> ${digest}"
done

# -- Apply ingresses so new routes always exist before pods come up -----------
# These are idempotent and intentionally re-applied every deploy so a config
# drift between what the ingress-nginx controller is serving and what main
# declares never has time to compound (same step as the deploy workflow).
if [ "${DRY_RUN}" = "1" ]; then
  echo "[dry] kubectl apply -f infra/k8s-vke/ingress-vke.yaml"
  echo "[dry] kubectl apply -f infra/k8s-vke/ingress-ip.yaml"
else
  kubectl apply -f infra/k8s-vke/ingress-vke.yaml
  kubectl apply -f infra/k8s-vke/ingress-ip.yaml
fi

# -- Roll deployments to the immutable digest --------------------------------
rolled_services=()
for svc in ${SERVICES}; do
  digest_file="${DIGEST_DIR}/${svc}.digest"
  digest="$(tr -d '[:space:]' < "${digest_file}")"
  image_ref="${REGISTRY}/${svc}@${digest}"
  echo "------------------------------------------------------------"
  echo "rolling deployment/${svc} to ${image_ref}"
  if [ "${DRY_RUN}" = "1" ]; then
    echo "[dry] kubectl -n ${NAMESPACE} set image deployment/${svc} ${svc}=${image_ref}"
    echo "[dry] kubectl -n ${NAMESPACE} rollout status deployment/${svc} --timeout=600s"
  else
    kubectl -n "${NAMESPACE}" set image "deployment/${svc}" "${svc}=${image_ref}"
    kubectl -n "${NAMESPACE}" rollout status "deployment/${svc}" --timeout=600s
    rolled_services+=("${svc}")
  fi
done

echo "============================================================"
echo "deploy complete. rolled: ${SERVICES}"
echo "verifying digests via scripts/post_deploy_smoke.sh ..."
echo "============================================================"

if [ "${DRY_RUN}" = "1" ]; then
  echo "[dry] DIGEST_DIR=${DIGEST_DIR} NS=${NAMESPACE} SERVICES='${SERVICES}' bash scripts/post_deploy_smoke.sh"
  exit 0
fi

# Auto-rollback only the deployments THIS run touched. An earlier failure (eg
# missing creds) must not undo revisions that are already serving traffic.
if ! DIGEST_DIR="${DIGEST_DIR}" NS="${NAMESPACE}" SERVICES="${SERVICES}" \
       bash scripts/post_deploy_smoke.sh; then
  echo "::error:: digest smoke failed. Rolling back ${rolled_services[*]:-<none>}" >&2
  for svc in "${rolled_services[@]}"; do
    kubectl -n "${NAMESPACE}" rollout undo "deployment/${svc}" || \
      echo "rollback ${svc} skipped"
  done
  exit 5
fi

echo
echo "SUCCESS."
echo "  identity + web pinned at ${TAG} (sha256 digest in ${DIGEST_DIR})"
echo "  verify public endpoints after DNS cache:"
echo "    curl -sS https://api.salareen.com/version"
echo "    curl -sS https://www.salareen.com/version"
echo
echo "  Expected version string: v0.66.0 (see apps/web/app/lib/version.ts)."
