#!/usr/bin/env bash
# One-time: install Expo Go on a running Android emulator (needs network).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(dirname "$0")"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$SCRIPT_DIR/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$SCRIPT_DIR/mobile-sim-utils.sh"

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
echo "  Check network/VPN, then run: bash scripts/mobile-install-expo-go-android.sh" >&2
exit 1
