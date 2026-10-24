#!/usr/bin/env bash
# deploy_service.sh - deploy ONE image-based component to the VKE cluster and PROVE it is the code we meant.
#
# Usage:  scripts/deploy_service.sh <component> [--sha SHA] [--dry-run] [--no-release] [--skip-capacity]
#                                    [--allow-same-digest] [--allow-unmerged]
#   components are defined in scripts/train/components.conf (web, course-studio, children-lab, curriculum, ...).
#
# Why this exists (two real incidents):
#   * In zsh an unbraced "$d:latest" expands as "${d:l}atest", so images were pushed to repositories such as
#     "course-studioatest" while the cluster kept restarting the old ones. Here every variable is braced, the script
#     is bash (never sourced into zsh), and the registry digest MUST change after the push.
#   * "Deployed" was assumed without looking. Here the pod's imageID must equal the digest we pushed.
#
# Steps: lock -> checks -> capacity gate -> build+push (explicit tags, revision label) -> digest changed ->
#        label contains the commit -> rollout restart + status -> pods run the pushed digest -> smoke ->
#        record GitHub deployment + release.  On ANY failure after the push: re-point :latest at the previous
#        digest (rollout undo cannot help with a mutable :latest tag), restart, record a failed deployment.
#
# Env: REGISTRY (default sjc.vultrcr.com/salareen)  NS (aoep)  BASE_URL (https://www.salareen.com)
#      ROLLOUT_TIMEOUT (480s)  MAX_CPU_PCT/MAX_MEM_PCT (90)  TRAIN_DIR (output/train)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
# A git hook or an outer repo may export GIT_DIR / GIT_INDEX_FILE; never let them redirect our git calls.
for _v in $(compgen -e | grep '^GIT_' || true); do unset "${_v}"; done

REGISTRY="${REGISTRY:-sjc.vultrcr.com/salareen}"
NS="${NS:-aoep}"
BASE_URL="${BASE_URL:-https://www.salareen.com}"
ROLLOUT_TIMEOUT="${ROLLOUT_TIMEOUT:-480s}"
TRAIN_DIR="${TRAIN_DIR:-${ROOT}/output/train}"
CONF="${COMPONENTS_CONF:-${ROOT}/scripts/train/components.conf}"

COMPONENT=""
SHA=""
DRY=0
RELEASE=1
CAPACITY=1
ALLOW_SAME=0
ALLOW_UNMERGED=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sha) SHA="${2:?--sha needs a value}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --no-release) RELEASE=0; shift ;;
    --skip-capacity) CAPACITY=0; shift ;;
    --allow-same-digest) ALLOW_SAME=1; shift ;;
    --allow-unmerged) ALLOW_UNMERGED=1; shift ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) COMPONENT="$1"; shift ;;
  esac
done
[ -n "${COMPONENT}" ] || { echo "usage: deploy_service.sh <component> [flags]" >&2; exit 2; }

log() { printf '[deploy %s] %s\n' "${COMPONENT}" "$*"; }
die() { printf '[deploy %s] ERROR: %s\n' "${COMPONENT}" "$*" >&2; exit 1; }

# run: print in dry-run mode, execute otherwise.
run() {
  if [ "${DRY}" = "1" ]; then printf '+ %s\n' "$*"; return 0; fi
  "$@"
}

# ---- component lookup (exact match on the first field; no globbing) ----
LINE="$(awk -F'|' -v want="${COMPONENT}" '/^[[:space:]]*#/ {next} $1 == want {print; exit}' "${CONF}")"
[ -n "${LINE}" ] || die "unknown component '${COMPONENT}' (see ${CONF})"
IFS='|' read -r _NAME DOCKERFILE DEPLOYMENT SMOKE_PATHS _PREFIXES <<<"${LINE}"
REPO="${REGISTRY}/${DEPLOYMENT}"
TAG_LATEST="${REPO}:latest"
[ -f "${ROOT}/${DOCKERFILE}" ] || die "Dockerfile missing: ${DOCKERFILE}"

# ---- lock: never two deploys at once ----
mkdir -p "${TRAIN_DIR}"
LOCK_DIR="${TRAIN_DIR}/deploy.lock.d"
if [ "${DRY}" = "0" ]; then
  if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
    OLD_PID="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"
    if [ -n "${OLD_PID}" ] && kill -0 "${OLD_PID}" 2>/dev/null; then
      die "another deploy is running (pid ${OLD_PID})"
    fi
    log "removing stale lock (pid ${OLD_PID:-unknown})"
    rm -rf "${LOCK_DIR}"; mkdir "${LOCK_DIR}"
  fi
  echo "$$" > "${LOCK_DIR}/pid"
  trap 'rm -rf "${LOCK_DIR}"' EXIT
fi

# ---- pause switch ----
[ ! -e "${ROOT}/scripts/train/PAUSE" ] || die "scripts/train/PAUSE exists: deploys are paused"

# ---- which commit? it must be HEAD, clean, and on origin/main ----
HEAD_SHA="$(git rev-parse HEAD)"
SHA="${SHA:-${HEAD_SHA}}"
SHA="$(git rev-parse --verify "${SHA}^{commit}")"
[ "${SHA}" = "${HEAD_SHA}" ] || die "building the working tree: HEAD is ${HEAD_SHA:0:8} but --sha is ${SHA:0:8}; check out ${SHA:0:8} first"
if ! git diff --quiet || ! git diff --cached --quiet; then die "tracked files have uncommitted changes"; fi
if [ "${ALLOW_UNMERGED}" = "0" ]; then
  git fetch -q origin main || die "cannot fetch origin/main"
  git merge-base --is-ancestor "${SHA}" origin/main || die "${SHA:0:8} is not on origin/main (use --allow-unmerged only for a deliberate hotfix)"
fi
SHA12="${SHA:0:12}"
VERSION_NOW="$(tr -d '[:space:]' < "${ROOT}/VERSION")"
TAG_SHA="${REPO}:${SHA12}"
log "component=${COMPONENT} deployment=${DEPLOYMENT} sha=${SHA12} version=${VERSION_NOW} dry_run=${DRY}"

# ---- capacity gate: only a few nodes are usable ----
if [ "${CAPACITY}" = "1" ]; then
  if [ "${DRY}" = "1" ]; then
    echo "+ python3 scripts/node_analyzer.py --json | python3 scripts/train/capacity_gate.py ${MAX_CPU_PCT:-90} ${MAX_MEM_PCT:-90}"
  else
    python3 "${ROOT}/scripts/node_analyzer.py" --json | python3 "${ROOT}/scripts/train/capacity_gate.py" "${MAX_CPU_PCT:-90}" "${MAX_MEM_PCT:-90}" \
      || die "capacity gate refused this rollout"
  fi
fi

registry_digest() { # $1 = image reference; prints sha256:... or nothing
  docker buildx imagetools inspect "$1" 2>/dev/null | awk '/^Digest:/ {print $2; exit}'
}

BEFORE=""
if [ "${DRY}" = "1" ]; then
  echo "+ docker buildx imagetools inspect ${TAG_LATEST}   # digest BEFORE"
else
  BEFORE="$(registry_digest "${TAG_LATEST}" || true)"
  log "registry digest before: ${BEFORE:-none}"
fi

rollback() {
  local why="$1"
  log "FAILURE: ${why}"
  if [ -n "${BEFORE}" ]; then
    log "re-pointing ${TAG_LATEST} at the previous digest ${BEFORE:0:19}"
    docker buildx imagetools create --tag "${TAG_LATEST}" "${REPO}@${BEFORE}" || log "WARNING: could not re-tag the previous image"
    kubectl -n "${NS}" rollout restart "deploy/${DEPLOYMENT}" || true
    kubectl -n "${NS}" rollout status "deploy/${DEPLOYMENT}" --timeout="${ROLLOUT_TIMEOUT}" || true
  else
    log "no previous digest recorded; leaving the deployment as is"
  fi
  "${ROOT}/scripts/record_deployment.sh" "${SHA}" "FAILED ${COMPONENT} v${VERSION_NOW}: ${why}" failure || true
  exit 1
}

# ---- build + push with explicit, braced tags and a revision label ----
run docker buildx build --platform linux/amd64 --no-cache --pull \
  --label "org.opencontainers.image.revision=${SHA}" \
  --label "org.opencontainers.image.version=${VERSION_NOW}" \
  -t "${TAG_LATEST}" -t "${TAG_SHA}" \
  -f "${ROOT}/${DOCKERFILE}" --push "${ROOT}"

AFTER=""
if [ "${DRY}" = "1" ]; then
  echo "+ assert registry digest of ${TAG_LATEST} changed (before != after)"
  echo "+ assert image config label org.opencontainers.image.revision contains ${SHA}"
else
  AFTER="$(registry_digest "${TAG_LATEST}" || true)"
  [ -n "${AFTER}" ] || rollback "cannot read the registry digest after the push"
  if [ "${AFTER}" = "${BEFORE}" ] && [ "${ALLOW_SAME}" = "0" ]; then
    rollback "registry digest unchanged (${AFTER:0:19}): the push did not update ${TAG_LATEST}"
  fi
  CONFIG="$(docker buildx imagetools inspect "${REPO}@${AFTER}" --format '{{json .Image}}' 2>/dev/null || true)"
  case "${CONFIG}" in
    *"${SHA}"*) log "image label carries commit ${SHA12}" ;;
    *) rollback "the pushed image does not carry commit ${SHA12} in its revision label" ;;
  esac
fi

# ---- roll out and verify the PODS run the digest we pushed ----
run kubectl -n "${NS}" rollout restart "deploy/${DEPLOYMENT}"
if [ "${DRY}" = "0" ]; then
  kubectl -n "${NS}" rollout status "deploy/${DEPLOYMENT}" --timeout="${ROLLOUT_TIMEOUT}" || rollback "rollout did not finish in ${ROLLOUT_TIMEOUT}"
  IMAGE_IDS="$(kubectl -n "${NS}" get pods -l "app=${DEPLOYMENT}" --field-selector=status.phase=Running \
    -o jsonpath='{range .items[*]}{.status.containerStatuses[0].imageID}{"\n"}{end}' 2>/dev/null | sed '/^$/d' || true)"
  [ -n "${IMAGE_IDS}" ] || rollback "no running pods found for app=${DEPLOYMENT} (cannot verify the image)"
  while IFS= read -r id; do
    case "${id}" in
      *"@${AFTER}") ;;
      *) rollback "a pod runs ${id}, not the pushed digest ${AFTER:0:19}" ;;
    esac
  done <<<"${IMAGE_IDS}"
  log "all pods run ${AFTER:0:19}"
else
  echo "+ kubectl -n ${NS} rollout status deploy/${DEPLOYMENT} --timeout=${ROLLOUT_TIMEOUT}"
  echo "+ assert every running pod imageID ends with @<pushed digest>"
fi

# ---- smoke: key URLs below 400, and no 5xx across repeated hits of the first path ----
IFS=',' read -r -a PATHS <<<"${SMOKE_PATHS}"
for p in "${PATHS[@]}"; do
  [ -n "${p}" ] || continue
  if [ "${DRY}" = "1" ]; then echo "+ curl ${BASE_URL}${p}   # must be < 400"; continue; fi
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${BASE_URL}${p}" || echo 000)"
  case "${code}" in
    2??|3??) log "smoke ${p} -> ${code}" ;;
    *) rollback "smoke ${p} returned ${code}" ;;
  esac
done
FIRST="${PATHS[0]:-/}"
if [ "${DRY}" = "1" ]; then
  echo "+ 10x curl ${BASE_URL}${FIRST}   # no 5xx"
else
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${BASE_URL}${FIRST}" || echo 000)"
    case "${code}" in 5??|000) rollback "repeat hit of ${FIRST} returned ${code}" ;; esac
  done
fi

# ---- record the REAL result ----
run "${ROOT}/scripts/record_deployment.sh" "${SHA}" "${COMPONENT} v${VERSION_NOW} deployed, digest-verified (${AFTER:0:19})" success
if [ "${RELEASE}" = "1" ]; then run python3 "${ROOT}/scripts/publish_release.py"; fi
log "done"
