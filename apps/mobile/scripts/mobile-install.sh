#!/usr/bin/env bash
# Reliable pnpm install for apps/mobile — removes stale node_modules when .bin is missing.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
MOBILE_ROOT="$ROOT"
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
PNPM_FLAGS=(
  --force
  --config.optimistic-repeat-install=false
  --config.node-linker=hoisted
  --config.package-import-method=copy
)

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

if ! mobile_deps_has_metro_local_node_modules; then
  echo "    external pnpm symlinks detected — materializing Metro-local copies"
  mobile_deps_ensure_metro_local || true
fi

if ! mobile_deps_has_babel_runtime; then
  echo "    @babel/runtime missing or symlinked outside project — retry with copy"
  rm -rf node_modules
  pnpm install "${PNPM_FLAGS[@]}" || true
fi

if ! mobile_deps_has_metro_local_node_modules; then
  echo "    materializing all external symlinks for Metro"
  mobile_deps_ensure_metro_local || true
fi

if ! mobile_deps_has_babel_runtime && command -v npm >/dev/null 2>&1; then
  echo "    falling back to npm install for @babel/runtime (Metro-local copy)"
  rm -rf node_modules
  npm install --legacy-peer-deps
fi

if ! mobile_deps_has_babel_runtime; then
  echo "ERROR: @babel/runtime must live under apps/mobile/node_modules (Metro red screen if not)." >&2
  mobile_deps_print_status >&2
  exit 1
fi

if ! mobile_deps_has_metro_local_node_modules; then
  echo "ERROR: node_modules still has symlinks outside apps/mobile — Metro cannot bundle." >&2
  mobile_deps_print_status >&2
  echo "  Fix: node scripts/ensure-metro-local-deps.js" >&2
  exit 1
fi

if ! mobile_deps_has_expo; then
  echo "WARN: expo not found after install — dev server may fail." >&2
  mobile_deps_print_status >&2
else
  ok_msg="expo + typescript + @babel/runtime present"
fi

echo "OK install (${ok_msg:-typescript present})"
mobile_deps_print_status

node scripts/patch-expo-localization-ios.js || true
node scripts/patch-expo-device-ios.js || true

node scripts/patch-react-native-runtimescheduler-ios.js || true

node scripts/ensure-metro-local-deps.js || true
if [[ -d ios ]]; then
  bash scripts/mobile-ios-pod-refresh.sh || true
fi
