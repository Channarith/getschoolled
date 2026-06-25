#!/usr/bin/env bash
# Run Expo CLI directly (no pnpm exec) with heap headroom for Metro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"

if [ -e node_modules/.bin/expo ]; then
  exec node_modules/.bin/expo "$@"
fi
if [ -f node_modules/expo/bin/cli ]; then
  exec node node_modules/expo/bin/cli "$@"
fi

echo "ERROR: expo not installed — run: bash scripts/mobile-install.sh" >&2
exit 1
