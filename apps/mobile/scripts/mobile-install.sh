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

if [ -d node_modules ] && ! mobile_deps_has_tsc; then
  echo "    node_modules present but typescript/tsc missing — removing stale tree"
  rm -rf node_modules
fi

if [ ! -d node_modules ]; then
  echo "    running pnpm install (fresh)..."
  pnpm install --force
else
  echo "    running pnpm install..."
  pnpm install --force
fi

if ! mobile_deps_has_tsc; then
  echo "ERROR: pnpm install finished but tsc is still missing." >&2
  mobile_deps_print_status >&2
  echo "  Try: rm -rf node_modules && pnpm store prune && pnpm install --force" >&2
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
