#!/usr/bin/env bash
# Mobile typecheck with preflight — avoids OOM from stale **/*.ts tsconfig includes.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MOBILE_ROOT="$ROOT"
. "$(dirname "$0")/mobile-deps.sh"

TSCONFIG="${TSCONFIG:-tsconfig.typecheck.json}"
VERBOSE="${VERBOSE:-0}"

echo "==> mobile typecheck"
echo "    cwd=$PWD"
echo "    config=$TSCONFIG"

if [ ! -f "$TSCONFIG" ]; then
  echo "ERROR: missing $TSCONFIG — git pull origin main" >&2
  exit 1
fi

if [ ! -f app.json ]; then
  echo "ERROR: not in the mobile app directory." >&2
  echo "  Monorepo path:  cd path/to/getschoolled/apps/mobile" >&2
  echo "  You are in:     $PWD" >&2
  exit 1
fi

if grep -qE '"\*\*/\*\.(ts|tsx)"' tsconfig.json 2>/dev/null; then
  echo "ERROR: tsconfig.json still has \"**/*.ts\" include (OOM)." >&2
  echo "  git pull origin main" >&2
  exit 1
fi

SRC_TS_COUNT="$(find src -name '*.ts' -o -name '*.tsx' 2>/dev/null | wc -l | tr -d ' ')"
echo "    source files under src/: ${SRC_TS_COUNT} (expect ~20)"

if [ "${SRC_TS_COUNT}" -gt 200 ]; then
  echo "ERROR: too many .ts files under src/" >&2
  exit 1
fi

if ! mobile_deps_has_tsc; then
  echo "ERROR: typescript/tsc not found after pnpm install." >&2
  mobile_deps_print_status >&2
  mobile_deps_install_hint >&2
  exit 1
fi

if [ "$VERBOSE" = "1" ]; then
  echo "    tsconfig include:"
  grep -A6 '"include"' tsconfig.json 2>/dev/null || true
  echo "    (verbose uses find only — NOT tsc --listFilesOnly, which can OOM on Mac)"
  mobile_deps_print_status
fi

# 4 GB default Node heap is tight for RN type graphs on some Mac/Node 22 builds.
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}"

echo "    running tsc (NODE_OPTIONS=$NODE_OPTIONS)..."
if [ -f node_modules/typescript/lib/tsc.js ]; then
  node node_modules/typescript/lib/tsc.js --noEmit -p "$TSCONFIG"
elif [ -e node_modules/.bin/tsc ]; then
  node_modules/.bin/tsc --noEmit -p "$TSCONFIG"
else
  echo "ERROR: could not locate tsc" >&2
  exit 1
fi
echo "OK typecheck"
