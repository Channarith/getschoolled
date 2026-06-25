#!/usr/bin/env bash
# Refresh CocoaPods after Metro-local node_modules (avoids pnpm paths in Pods.xcodeproj).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"

if [[ ! -d ios ]]; then
  echo "ERROR: ios/ missing — run: npx expo prebuild --platform ios" >&2
  exit 1
fi

node scripts/ensure-metro-local-deps.js
node scripts/patch-expo-localization-ios.js
node scripts/patch-expo-device-ios.js
node scripts/patch-react-native-runtimescheduler-ios.js

PBX="ios/Pods/Pods.xcodeproj/project.pbxproj"
needs_pod=0
if [[ ! -f "$PBX" ]]; then
  needs_pod=1
elif grep -q 'node_modules/\.pnpm/react-native' "$PBX" 2>/dev/null; then
  echo "==> Pods.xcodeproj still references pnpm react-native — pod install required"
  needs_pod=1
fi

if [[ "$needs_pod" == "1" ]] || [[ "${FORCE_POD_INSTALL:-0}" == "1" ]]; then
  echo "==> pod install (cwd=$ROOT/ios)"
  (
    cd ios
    pod install
  )
else
  echo "==> Pods OK (local react-native paths)"
fi
