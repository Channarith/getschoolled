#!/usr/bin/env bash
# One-time: download and install Expo Go on the booted iOS simulator (needs network).
# After this, launch scripts use EXPO_OFFLINE=1 and skip the expo.dev bundled-modules fetch.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(dirname "$0")"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$SCRIPT_DIR/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$SCRIPT_DIR/mobile-sim-utils.sh"

if mobile_ios_expo_go_installed; then
  echo "OK Expo Go already on simulator"
  exit 0
fi

echo "==> Installing Expo Go on iOS Simulator (one-time, needs network)"
mobile_ios_boot_simulator 2>/dev/null || true
bash "$SCRIPT_DIR/mobile-metro-cleanup.sh"

unset EXPO_OFFLINE
export CI=false
export EXPO_DEBUG="${EXPO_DEBUG:-1}"
export DEBUG="${DEBUG:-expo:*}"

echo "    Starting temporary Metro on port 8082 to trigger Expo Go download…"
bash "$SCRIPT_DIR/mobile-expo.sh" start --ios --port 8082 --localhost &
metro_pid=$!
cleanup() {
  kill "$metro_pid" 2>/dev/null || true
  bash "$SCRIPT_DIR/mobile-metro-cleanup.sh" 2>/dev/null || true
}
trap cleanup EXIT

for i in $(seq 1 90); do
  if mobile_ios_expo_go_installed; then
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
echo "  Check network/VPN, then run: bash scripts/mobile-install-expo-go-ios.sh" >&2
exit 1
