#!/usr/bin/env bash
# Reliable pnpm install for apps/mobile — removes stale node_modules when .bin is missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}"

. "$(dirname "$0")/mobile-deps.sh"

echo "==> mobile install"
echo "    cwd=$PWD"
echo "    NODE_OPTIONS=$NODE_OPTIONS"
echo "    pnpm $(pnpm --version 2>/dev/null || echo unknown)"

if [ ! -f package.json ] || [ ! -f pnpm-lock.yaml ]; then
  echo "ERROR: package.json or pnpm-lock.yaml missing in $PWD" >&2
  exit 1
fi

if [ ! -f app.json ]; then
  echo "ERROR: not in apps/mobile (app.json missing)" >&2
  exit 1
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "ERROR: pnpm not on PATH — install: npm i -g pnpm" >&2
  exit 1
fi

if [ ! -f .npmrc ]; then
  echo "WARN: .npmrc missing — copy from repo (needs node-linker=hoisted)" >&2
fi

# pnpm v11 optimisticRepeatInstall can print "Already up to date" without creating
# node_modules after a deleted tree — force a real link pass.
PNPM_FLAGS=(--force --config.optimistic-repeat-install=false --config.node-linker=hoisted)

if [ -d node_modules ] && ! mobile_deps_has_tsc; then
  echo "    node_modules present but typescript/tsc missing — removing stale tree"
  rm -rf node_modules
fi

if [ ! -d node_modules ]; then
  echo "    running pnpm install (fresh, optimistic-repeat-install=false)..."
else
  echo "    running pnpm install (optimistic-repeat-install=false)..."
fi

if ! pnpm install "${PNPM_FLAGS[@]}"; then
  echo "WARN: pnpm install failed — trying npm install fallback" >&2
  if command -v npm >/dev/null 2>&1; then
    npm install --legacy-peer-deps
  else
    echo "ERROR: pnpm install failed and npm not available" >&2
    exit 1
  fi
fi

if ! mobile_deps_has_tsc; then
  echo "    pnpm did not link tsc — retry after clearing local linker state"
  rm -rf node_modules
  pnpm install "${PNPM_FLAGS[@]}" --config.package-import-method=copy || true
fi

if ! mobile_deps_has_tsc && command -v npm >/dev/null 2>&1; then
  echo "    falling back to npm install --legacy-peer-deps"
  rm -rf node_modules
  npm install --legacy-peer-deps
fi

if ! mobile_deps_has_tsc; then
  echo "ERROR: install finished but tsc is still missing." >&2
  mobile_deps_print_status >&2
  echo "  Manual fix:" >&2
  echo "    rm -rf node_modules && pnpm install --config.optimistic-repeat-install=false --force" >&2
  exit 1
fi

if ! mobile_deps_has_expo; then
  echo "WARN: expo not found after install — dev server may fail." >&2
  mobile_deps_print_status >&2
else
  ok_msg="expo + typescript present"
fi

echo "OK install (${ok_msg:-typescript present})"
mobile_deps_print_status
