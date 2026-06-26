#!/usr/bin/env bash
# One-time: download and install Expo Go on the booted iOS simulator (needs network).
# After this, launch scripts use EXPO_OFFLINE=1 and skip the expo.dev bundled-modules fetch.
#
# Usage:
#   bash scripts/mobile-install-expo-go-ios.sh              # direct CDN download (preferred)
#   bash scripts/mobile-install-expo-go-ios.sh --metro-fallback   # old Metro-based install
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
    -h|--help)
      echo "Usage: $0 [--metro-fallback]"
      echo "  Default: direct download via Expo CDN (no Metro, faster, avoids bundled-modules hang)"
      echo "  --metro-fallback: start temporary Metro on 8082 (legacy path)"
      exit 0
      ;;
  esac
done

if mobile_ios_expo_go_installed; then
  echo "OK Expo Go already on simulator"
  exit 0
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS Simulator requires macOS." >&2
  exit 1
fi

echo "==> Installing Expo Go on iOS Simulator (one-time, needs network)"
mobile_ios_boot_simulator 2>/dev/null || true

if [[ "$USE_METRO_FALLBACK" != "1" ]]; then
  echo "    Method: direct CDN download (recommended)"
  unset EXPO_OFFLINE
  export CI=false
  direct_rc=0
  node "$SCRIPT_DIR/mobile-install-expo-go-direct.js" ios || direct_rc=$?
  if [[ "$direct_rc" -eq 0 ]] && mobile_ios_expo_go_installed; then
    echo "OK Expo Go installed"
    exit 0
  fi
  if [[ "$direct_rc" -ne 0 ]]; then
    echo "WARN: direct CDN install failed (exit ${direct_rc}) — trying Metro fallback…" >&2
  else
    echo "WARN: download finished but Expo Go not detected on simulator — trying Metro fallback…" >&2
  fi
fi

echo "    Method: Metro fallback (temporary server on port 8082)"
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
echo "  Manual: https://expo.dev/go?platform=ios&sdkVersion=$(mobile_expo_sdk_version 2>/dev/null || echo 51)" >&2
echo "  Or retry: bash scripts/mobile-install-expo-go-ios.sh" >&2
exit 1
