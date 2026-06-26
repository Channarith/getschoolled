#!/usr/bin/env bash
# CI guard: every PR targeting main must advance VERSION vs the merge base.
set -euo pipefail

BASE_REF="${GITHUB_BASE_REF:-main}"
# GitHub Actions: pass PR_BASE_SHA=${{ github.event.pull_request.base.sha }} in the workflow.
BASE_SHA="${PR_BASE_SHA:-}"

if [ -z "${GITHUB_EVENT_NAME:-}" ] || [ "${GITHUB_EVENT_NAME}" != "pull_request" ]; then
  echo "Skipping version-bump check (not a pull_request event)."
  exit 0
fi

resolve_base_ref() {
  if [ -n "${BASE_SHA}" ]; then
    echo "${BASE_SHA}"
    return 0
  fi
  # Shallow fetch is enough to read VERSION at the base tip.
  if ! git fetch origin "${BASE_REF}" --depth=1 2>/dev/null; then
    git fetch origin "${BASE_REF}" 2>/dev/null || true
  fi
  if git rev-parse --verify "origin/${BASE_REF}" >/dev/null 2>&1; then
    git rev-parse "origin/${BASE_REF}"
    return 0
  fi
  if git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1; then
    git rev-parse "${BASE_REF}"
    return 0
  fi
  echo "::error::Cannot resolve base ref for ${BASE_REF}. Set PR_BASE_SHA in the workflow or fetch-depth: 0." >&2
  return 1
}

BASE_REF_SHA="$(resolve_base_ref)"

BASE_VERSION="$(git show "${BASE_REF_SHA}:VERSION" 2>/dev/null | tr -d '[:space:]' || echo "")"
HEAD_VERSION="$(tr -d '[:space:]' < VERSION)"

if [ -z "${BASE_VERSION}" ] || [ -z "${HEAD_VERSION}" ]; then
  echo "::error::Could not read VERSION on base (${BASE_REF_SHA}) or head."
  exit 1
fi

if [ "${HEAD_VERSION}" = "${BASE_VERSION}" ]; then
  echo "::error::VERSION must be bumped on every PR merging to main."
  echo "Base ${BASE_REF} (${BASE_REF_SHA:0:12}) is ${BASE_VERSION}; PR still ${HEAD_VERSION}."
  echo "Run: python3 scripts/bump_pr_version.py"
  exit 1
fi

WEB_VERSION="$(grep 'GENERATED_VERSION = "' apps/web/app/lib/version.ts | sed 's/.*"\([^"]*\)".*/\1/')"
if [ "${WEB_VERSION}" != "${HEAD_VERSION}" ]; then
  echo "::error::apps/web/app/lib/version.ts GENERATED_VERSION (${WEB_VERSION}) must match VERSION (${HEAD_VERSION})."
  echo "Re-run: python3 scripts/bump_pr_version.py"
  exit 1
fi

echo "VERSION bumped: ${BASE_VERSION} -> ${HEAD_VERSION} (base ${BASE_REF} @ ${BASE_REF_SHA:0:12})"
