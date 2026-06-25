#!/usr/bin/env bash
# Verbose native Android debug build via Gradle (after prebuild).
#
# Usage (from apps/mobile):
#   bash scripts/mobile-gradle-debug.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d android ]]; then
  echo "ERROR: apps/mobile/android/ not found." >&2
  echo "  Generate native projects first:" >&2
  echo "    cd apps/mobile && pnpm run prebuild" >&2
  echo "  Or: pnpm run android:debug" >&2
  exit 1
fi

echo "==> Gradle assembleDebug (verbose)"
node scripts/patch-gradle-wrapper.js
cd android
./gradlew assembleDebug --info --stacktrace
