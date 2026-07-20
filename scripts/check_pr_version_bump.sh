#!/usr/bin/env bash
# CI guard: EVERY PR must (1) advance VERSION and (2) document that version in
# the newest CHANGELOG.txt entry. This gives us end-to-end traceability -- every
# change on main maps to a distinct version and a changelog line that names it.
#
# Why compare against the MERGE-BASE (fork point) and not the base tip:
#   The old gate compared HEAD's VERSION to the CURRENT tip of main. When two PRs
#   both bumped to e.g. 0.9.1, whichever merged second saw base == 0.9.1 == its
#   own VERSION and failed even though it HAD bumped. Comparing against the fork
#   point instead asks the real question -- "did THIS branch advance VERSION vs
#   where it branched from?" -- so concurrent PRs never falsely collide. The
#   `maxver` merge driver (.gitattributes) then keeps main moving forward.
set -euo pipefail

BASE_REF="${GITHUB_BASE_REF:-main}"

# Only gate pull_request events in CI; skip other CI events. When run locally
# (no GITHUB_EVENT_NAME) we still perform the check against origin/<base>.
if [ -n "${GITHUB_EVENT_NAME:-}" ] && [ "${GITHUB_EVENT_NAME}" != "pull_request" ]; then
  echo "Skipping version-bump check (event=${GITHUB_EVENT_NAME}, not pull_request)."
  exit 0
fi

git fetch origin "${BASE_REF}" --quiet 2>/dev/null || true

resolve_merge_base() {
  local base
  for base in "origin/${BASE_REF}" "${BASE_REF}"; do
    if git rev-parse --verify "${base}" >/dev/null 2>&1; then
      git merge-base HEAD "${base}" 2>/dev/null && return 0
    fi
  done
  return 1
}

MERGE_BASE="$(resolve_merge_base || true)"
if [ -z "${MERGE_BASE}" ]; then
  echo "::warning::Could not resolve merge-base against ${BASE_REF}; skipping version-bump check."
  exit 0
fi

BASE_VERSION="$(git show "${MERGE_BASE}:VERSION" 2>/dev/null | tr -d '[:space:]' || echo "")"
HEAD_VERSION="$(tr -d '[:space:]' < VERSION)"

if [ -z "${BASE_VERSION}" ] || [ -z "${HEAD_VERSION}" ]; then
  echo "::error::Could not read VERSION on merge-base (${MERGE_BASE:0:12}) or head."
  exit 1
fi

# HEAD_VERSION must be STRICTLY greater than the fork-point version.
higher="$(printf '%s\n%s\n' "${BASE_VERSION}" "${HEAD_VERSION}" | sort -V | tail -1)"
if [ "${HEAD_VERSION}" = "${BASE_VERSION}" ] || [ "${higher}" != "${HEAD_VERSION}" ]; then
  echo "::error::VERSION must be bumped on every PR (traceability)."
  echo "Fork point (${MERGE_BASE:0:12}) is ${BASE_VERSION}; PR is ${HEAD_VERSION}."
  echo "Run: python3 scripts/bump_pr_version.py"
  exit 1
fi

# The generated version files must stay in lock-step with VERSION.
WEB_VERSION="$(grep 'GENERATED_VERSION = "' apps/web/app/lib/version.ts | sed 's/.*"\([^"]*\)".*/\1/')"
if [ "${WEB_VERSION}" != "${HEAD_VERSION}" ]; then
  echo "::error::apps/web/app/lib/version.ts (${WEB_VERSION}) must match VERSION (${HEAD_VERSION})."
  echo "Re-run: python3 scripts/bump_pr_version.py"
  exit 1
fi
if [ -f apps/mobile/src/version.ts ]; then
  MOBILE_VERSION="$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' apps/mobile/src/version.ts | head -1)"
  if [ "${MOBILE_VERSION}" != "${HEAD_VERSION}" ]; then
    echo "::error::apps/mobile/src/version.ts (${MOBILE_VERSION}) must match VERSION (${HEAD_VERSION})."
    echo "Re-run: python3 scripts/bump_pr_version.py"
    exit 1
  fi
fi

# The PR version must be DOCUMENTED in the most-recent changelog window.
# On GitHub pull_request runs, Actions checks out a synthetic merge commit
# (base branch as "ours"). With CHANGELOG union merges, base bullets can appear
# before PR bullets even when the PR version is newer, so checking only the
# single first bullet causes false failures. We therefore check that vX.Y.Z
# appears within the recent dated entries near the top of CHANGELOG.txt.
RECENT_DATED_ENTRIES="$(awk '
  /^- [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] - v[0-9]+\.[0-9]+\.[0-9]+ - / {
    print
    c++
    if (c >= 20) exit
  }
' CHANGELOG.txt)"
if ! printf '%s\n' "${RECENT_DATED_ENTRIES}" | grep -qF "v${HEAD_VERSION}"; then
  echo "::error::CHANGELOG.txt must document version ${HEAD_VERSION} near the top."
  echo "Use the format:  - YYYY-MM-DD - v${HEAD_VERSION} - <what changed>"
  exit 1
fi

echo "VERSION bumped: ${BASE_VERSION} -> ${HEAD_VERSION} (fork point ${MERGE_BASE:0:12})"
echo "changelog documents v${HEAD_VERSION}: ok"
