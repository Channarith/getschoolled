#!/usr/bin/env bash
# Standalone RELEASE Android APK: JS bundle embedded (no Metro / no localhost),
# backend pinned to the cloud/Vultr host. Installable on any device.
#
# Usage (from apps/mobile):
#   bash scripts/mobile-build-release-android.sh
#   MOBILE_CLOUD_BASE_URL=https://www.salareen.com bash scripts/mobile-build-release-android.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"

# Force cloud backend so the embedded bundle never points at localhost.
export MOBILE_DEPLOY_MODE=cloud
export MOBILE_CLOUD_BASE_URL="${MOBILE_CLOUD_BASE_URL:-https://www.salareen.com}"

echo "==> Standalone release APK"
echo "    backend: $MOBILE_CLOUD_BASE_URL (cloud)"

npm run native:prebuild:android

(
  cd android
  ./gradlew assembleRelease
)

APK="$ROOT/android/app/build/outputs/apk/release/app-release.apk"
if [[ -f "$APK" ]]; then
  echo ""
  echo "OK release APK: $APK"
  echo "Install on a connected device: adb install -r \"$APK\""
else
  echo "ERROR: release APK not found under android/app/build/outputs/apk/release/" >&2
  exit 1
fi
