#!/usr/bin/env bash
# One-command VKE deploy in the CORRECT order: build -> push -> apply -> restart.
#
# This encodes the hard-won ordering so the manual sequence isn't error-prone:
#   * apply -k runs AFTER the images are pushed and NEVER clobbers secrets
#     (aoep-secrets is managed out of band — see scripts/k8s_bootstrap_secrets.sh).
#   * the self-hosted LiveKit server is not deployed (Salareen uses LiveKit Cloud).
#
# Usage (from repo root, on the branch/commit you want to ship — usually main):
#   # log in once, or export creds so the script logs in for you:
#   export VULTR_REGISTRY_USERNAME=... VULTR_REGISTRY_PASSWORD=...
#   # first time on a fresh cluster only, so aoep-secrets exists:
#   export LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=...
#   bash scripts/deploy_vke.sh
#
# Env / flags:
#   REGISTRY   (default sjc.vultrcr.com/salareen)   TAG (default latest)
#   AOEP_NAMESPACE (default aoep)   PLATFORM (default linux/amd64)
#   SKIP_BUILD=1   build/push nothing (just apply + restart)
#   SKIP_APPLY=1   don't run `apply -k` (image-only redeploy; avoids re-applying config)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REGISTRY="${REGISTRY:-sjc.vultrcr.com/salareen}"
REGISTRY_HOST="${REGISTRY%%/*}"
TAG="${TAG:-latest}"
NS="${AOEP_NAMESPACE:-aoep}"
PLATFORM="${PLATFORM:-linux/amd64}"

# Services with a services/<name>/Dockerfile (web is handled separately).
SERVICES=(orchestrator speech perception memory curriculum billing integrations identity harvester)
# Deployments to roll (self-hosted livekit intentionally excluded — Cloud is used).
DEPLOYMENTS=(orchestrator web billing curriculum memory perception speech identity integrations harvester)

say() { printf "\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m  ! %s\033[0m\n" "$*"; }

command -v docker  >/dev/null || { echo "docker required"  >&2; exit 1; }
command -v kubectl >/dev/null || { echo "kubectl required (KUBECONFIG must point at the VKE cluster)" >&2; exit 1; }

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
SHA="$(git rev-parse --short HEAD 2>/dev/null || echo '?')"
say "Deploying ${BRANCH}@${SHA} -> ${REGISTRY}/*:${TAG}  (namespace=${NS})"
[ "$BRANCH" = "main" ] || warn "Not on 'main' — deploying the CURRENT checkout ($BRANCH)."
kubectl -n "$NS" get ns >/dev/null 2>&1 || kubectl get ns "$NS" >/dev/null 2>&1 || warn "namespace '$NS' not found yet."

# 1) Registry login (only if creds provided; otherwise assume already logged in).
if [ -n "${VULTR_REGISTRY_USERNAME:-}" ] && [ -n "${VULTR_REGISTRY_PASSWORD:-}" ]; then
  say "docker login $REGISTRY_HOST"
  printf '%s' "$VULTR_REGISTRY_PASSWORD" | docker login "$REGISTRY_HOST" -u "$VULTR_REGISTRY_USERNAME" --password-stdin
fi

# 2) Build + push all images for the cluster arch. ALWAYS a FRESH build
# (--no-cache --pull): a cached layer once shipped a stale orchestrator while the
# web image updated, so /api routes 404'd/405'd against old code. Fresh is the
# rule. Set BUILD_CACHE=1 to opt back into the layer cache for a fast iteration.
BUILD_FLAGS=(--platform "$PLATFORM")
if [ "${BUILD_CACHE:-0}" != "1" ]; then
  BUILD_FLAGS+=(--no-cache --pull)
fi
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  for svc in "${SERVICES[@]}"; do
    say "build+push $svc (fresh)"
    docker buildx build "${BUILD_FLAGS[@]}" -t "${REGISTRY}/${svc}:${TAG}" -f "services/${svc}/Dockerfile" --push .
  done
  say "build+push web (fresh)"
  docker buildx build "${BUILD_FLAGS[@]}" -t "${REGISTRY}/web:${TAG}" -f "apps/web/Dockerfile" --push .
else
  warn "SKIP_BUILD=1 — not building/pushing images."
fi

# 3) Ensure aoep-secrets exists (create-if-missing; never overwrites real values).
if [ -x "$ROOT/scripts/k8s_bootstrap_secrets.sh" ]; then
  say "ensure aoep-secrets exists (create-if-missing)"
  bash "$ROOT/scripts/k8s_bootstrap_secrets.sh" || warn "aoep-secrets not bootstrapped (export LIVEKIT_API_KEY/SECRET to auto-create on a fresh cluster)."
fi

# 4) One-time registry pull secret + default SA wiring (idempotent).
if [ -n "${VULTR_REGISTRY_USERNAME:-}" ] && [ -n "${VULTR_REGISTRY_PASSWORD:-}" ]; then
  say "ensure imagePullSecret 'vultr-registry'"
  kubectl -n "$NS" create secret docker-registry vultr-registry \
    --docker-server="$REGISTRY_HOST" \
    --docker-username="$VULTR_REGISTRY_USERNAME" \
    --docker-password="$VULTR_REGISTRY_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n "$NS" patch serviceaccount default \
    -p '{"imagePullSecrets":[{"name":"vultr-registry"}]}' >/dev/null
fi

# 5) Apply manifests (config + image tags). Does NOT touch aoep-secrets anymore.
if [ "${SKIP_APPLY:-0}" != "1" ]; then
  say "kubectl apply -k infra/k8s-vke"
  kubectl apply -k "$ROOT/infra/k8s-vke"
else
  warn "SKIP_APPLY=1 — not running apply -k (image-only redeploy)."
fi

# 5b) The web calls same-origin /orchestrator, /identity, /curriculum … which the
# 'aoep-apis' Ingress rewrites to each service. If it's missing, those POSTs fall
# through to the web app (Next.js) and return 404/405 — the exact "live class
# failures". Verify it exists.
if kubectl -n "$NS" get ingress aoep-apis >/dev/null 2>&1; then
  say "ingress aoep-apis present (/orchestrator, /identity, … routing OK)"
else
  warn "ingress 'aoep-apis' MISSING — /orchestrator API calls will 404/405. Re-run apply -k."
fi

# 6) Roll the deployments to the freshly pushed images.
if [ "$TAG" = "latest" ]; then
  # kustomize pins :latest + imagePullPolicy: Always, so a restart re-pulls it.
  for d in "${DEPLOYMENTS[@]}"; do
    kubectl -n "$NS" rollout restart "deploy/$d" 2>/dev/null || warn "no deploy/$d (skipping)"
  done
else
  # A specific tag: point each deployment at it (this triggers the rollout).
  for d in "${DEPLOYMENTS[@]}"; do
    kubectl -n "$NS" set image "deploy/$d" "$d=${REGISTRY}/$d:${TAG}" 2>/dev/null || warn "no deploy/$d (skipping)"
  done
fi

# 7) Wait for the critical ones, then show LiveKit wiring for a quick sanity check.
for d in orchestrator web identity; do
  kubectl -n "$NS" rollout status "deploy/$d" --timeout=240s || warn "deploy/$d did not become ready in time"
done

say "orchestrator LiveKit env (should be your Cloud project):"
kubectl -n "$NS" exec "deploy/orchestrator" -- printenv LIVEKIT_URL LIVEKIT_API_KEY 2>/dev/null || warn "could not read orchestrator env"

# Confirm the orchestrator is actually running the freshly built code (catches a
# stale image / cache-hit where the web updated but the API didn't).
say "deployed orchestrator /version (confirm it matches this checkout ${SHA}):"
kubectl -n "$NS" exec "deploy/orchestrator" -- \
  python3 -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/version', timeout=5).read().decode())" \
  2>/dev/null || warn "could not read orchestrator /version"
LOCAL_VER="$(cat "$ROOT/VERSION" 2>/dev/null || echo '?')"
say "this checkout VERSION: ${LOCAL_VER} — the line above should report the same version."

say "Deploy complete: ${REGISTRY}/*:${TAG} rolled to namespace ${NS}."
