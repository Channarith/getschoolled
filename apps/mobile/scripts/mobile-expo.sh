#!/usr/bin/env bash
# Run Expo CLI directly (no pnpm exec) with heap headroom for Metro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-deps.sh
MOBILE_ROOT="$ROOT"
. "$(dirname "$0")/mobile-deps.sh"

mobile_deps_ensure_metro_local || exit 1

# Stale Metro cache can 500 after materializing symlinked deps.
rm -rf node_modules/.cache/metro .expo/metro 2>/dev/null || true

# Native Android: patch settings.gradle before Gradle runs so @react-native/gradle-plugin
# resolves only under apps/mobile/node_modules (avoids duplicate :gradle-plugin when
# ~/node_modules/.pnpm also exists on the developer machine).
if [[ "${1:-}" == "run:android" ]] && [[ -d android ]]; then
  node scripts/patch-gradle-wrapper.js
fi

if [ -e node_modules/.bin/expo ]; then
  exec node_modules/.bin/expo "$@"
fi
if [ -f node_modules/expo/bin/cli ]; then
  exec node node_modules/expo/bin/cli "$@"
fi

echo "ERROR: expo not installed — run: bash scripts/mobile-install.sh" >&2
exit 1
