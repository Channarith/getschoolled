#!/usr/bin/env bash
# Mobile typecheck with preflight — avoids OOM from stale **/*.ts tsconfig includes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TSCONFIG="${TSCONFIG:-tsconfig.typecheck.json}"
VERBOSE="${VERBOSE:-0}"

echo "==> mobile typecheck (cwd=$PWD, config=$TSCONFIG)"

if [ ! -f "$TSCONFIG" ]; then
  echo "ERROR: missing $TSCONFIG" >&2
  exit 1
fi

if [ ! -f app.json ]; then
  echo "ERROR: run from apps/mobile (cd apps/mobile && pnpm run typecheck)" >&2
  exit 1
fi

# Fail fast if someone reverted to the config that scans all of node_modules.
if grep -qE '"\*\*/\*\.(ts|tsx)"' tsconfig.json 2>/dev/null; then
  echo "ERROR: apps/mobile/tsconfig.json still has \"**/*.ts\" include." >&2
  echo "  That typechecks node_modules and causes heap OOM (~7 min then abort)." >&2
  echo "  git pull origin main  OR  use include: App.tsx, index.ts, src/**/*.ts(x)" >&2
  exit 1
fi

SRC_TS_COUNT="$(find src -name '*.ts' -o -name '*.tsx' 2>/dev/null | wc -l | tr -d ' ')"
echo "    source files under src/: ${SRC_TS_COUNT} (expect ~20; thousands = wrong config/cwd)"

if [ "${SRC_TS_COUNT}" -gt 200 ]; then
  echo "ERROR: too many .ts files under src/ — wrong directory or generated junk?" >&2
  exit 1
fi

if [ ! -x node_modules/.bin/tsc ]; then
  echo "ERROR: node_modules/.bin/tsc missing — run: pnpm install" >&2
  exit 1
fi

TSC_CMD=(node_modules/.bin/tsc --noEmit -p "$TSCONFIG")
if [ "$VERBOSE" = "1" ]; then
  echo "    listing files tsc will load..."
  "${TSC_CMD[@]}" --listFilesOnly 2>/dev/null | tee /tmp/mobile-tsc-files.txt | wc -l | xargs echo "    listFiles count:"
  NM_COUNT="$(grep -c node_modules /tmp/mobile-tsc-files.txt 2>/dev/null || echo 0)"
  SRC_COUNT="$(grep -c '/src/' /tmp/mobile-tsc-files.txt 2>/dev/null || echo 0)"
  echo "    (node_modules libs ~${NM_COUNT} is normal; app src ~${SRC_COUNT})"
fi

echo "    running tsc..."
"${TSC_CMD[@]}"
echo "OK typecheck"
