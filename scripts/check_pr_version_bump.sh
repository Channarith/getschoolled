#!/usr/bin/env bash
# CI guard: every PR targeting main must advance VERSION vs the merge base.
set -euo pipefail

BASE_REF="${GITHUB_BASE_REF:-main}"
HEAD_REF="${GITHUB_HEAD_REF:-}"

if [ -z "${GITHUB_EVENT_NAME:-}" ] || [ "${GITHUB_EVENT_NAME}" != "pull_request" ]; then
  echo "Skipping version-bump check (not a pull_request event)."
  exit 0
fi

git fetch origin "${BASE_REF}" --depth=1 2>/dev/null || true
MERGE_BASE="$(git merge-base "origin/${BASE_REF}" HEAD 2>/dev/null || git merge-base "${BASE_REF}" HEAD)"

BASE_VERSION="$(git show "${MERGE_BASE}:VERSION" 2>/dev/null | tr -d '[:space:]' || echo "")"
HEAD_VERSION="$(tr -d '[:space:]' < VERSION)"

if [ -z "${BASE_VERSION}" ] || [ -z "${HEAD_VERSION}" ]; then
  echo "Could not read VERSION on base or head; failing closed."
  exit 1
fi

if [ "${HEAD_VERSION}" = "${BASE_VERSION}" ]; then
  echo "::error::VERSION must be bumped on every PR merging to main."
  echo "Base ${BASE_REF} is ${BASE_VERSION}; PR still ${HEAD_VERSION}."
  echo "Run: python3 scripts/bump_pr_version.py"
  exit 1
fi

WEB_VERSION="$(grep 'GENERATED_VERSION = "' apps/web/app/lib/version.ts | sed 's/.*"\([^"]*\)".*/\1/')"
if [ "${WEB_VERSION}" != "${HEAD_VERSION}" ]; then
  echo "::error::apps/web/app/lib/version.ts GENERATED_VERSION (${WEB_VERSION}) must match VERSION (${HEAD_VERSION})."
  echo "Re-run: python3 scripts/bump_pr_version.py"
  exit 1
fi

echo "VERSION bumped: ${BASE_VERSION} -> ${HEAD_VERSION}"
