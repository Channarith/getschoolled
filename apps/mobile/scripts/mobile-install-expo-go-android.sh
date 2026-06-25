#!/usr/bin/env bash
# One-time: install Expo Go on a running Android emulator (needs network).
#
# Usage:
#   bash scripts/mobile-install-expo-go-android.sh              # direct CDN download
#   bash scripts/mobile-install-expo-go-android.sh --metro-fallback
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(dirname "$0")"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$SCRIPT_DIR/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$SCRIPT_DIR/mobile-sim-utils.sh"
# shellcheck source=mobile-expo-go-utils.sh
. "$SCRIPT_DIR/mobile-expo-go-utils.sh"

USE_METRO_FALLBACK=0
for arg in "$@"; do
  case "$arg" in
    --metro-fallback) USE_METRO_FALLBACK=1 ;;
  esac
done

ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
ADB="$ANDROID_HOME/platform-tools/adb"

if ! "$ADB" devices 2>/dev/null | grep -q "emulator"; then
  echo "Boot an Android emulator first, then retry." >&2
  exit 1
fi

if mobile_android_expo_go_installed "$ADB"; then
  echo "OK Expo Go already on emulator"
  exit 0
fi

echo "==> Installing Expo Go on Android emulator (one-time, needs network)"

if [[ "$USE_METRO_FALLBACK" != "1" ]]; then
  echo "    Method: direct CDN download (recommended)"
  unset EXPO_OFFLINE
  export CI=false
  if node "$SCRIPT_DIR/mobile-install-expo-go-direct.js" android; then
    if mobile_android_expo_go_installed "$ADB"; then
      echo "OK Expo Go installed"
      exit 0
    fi
  fi
  echo "WARN: direct install did not verify — trying Metro fallback…" >&2
fi

echo "    Method: Metro fallback (temporary server on port 8082)"
bash "$SCRIPT_DIR/mobile-metro-cleanup.sh"

unset EXPO_OFFLINE
export CI=false
export EXPO_DEBUG="${EXPO_DEBUG:-1}"
export DEBUG="${DEBUG:-expo:*}"

bash "$SCRIPT_DIR/mobile-expo.sh" start --android --port 8082 &
metro_pid=$!
cleanup() {
  kill "$metro_pid" 2>/dev/null || true
  bash "$SCRIPT_DIR/mobile-metro-cleanup.sh" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 90); do
  if mobile_android_expo_go_installed "$ADB"; then
    echo "OK Expo Go installed ($((i * 2))s)"
    exit 0
  fi
  if ! kill -0 "$metro_pid" 2>/dev/null; then
    echo "WARN: Metro exited before Expo Go finished installing" >&2
    break
  fi
  sleep 2
done

echo "FAIL: Expo Go not installed after 3 min." >&2
echo "  Manual: https://expo.dev/go?platform=android&sdkVersion=$(mobile_expo_sdk_version 2>/dev/null || echo 51)" >&2
echo "  Or retry: bash scripts/mobile-install-expo-go-android.sh" >&2
exit 1
