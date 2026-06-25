#!/usr/bin/env bash
# Launch Salareen mobile on Android emulator with optional verbose Expo logs.
# Usage:
#   bash apps/mobile/scripts/mobile-launch-android.sh
#   bash apps/mobile/scripts/mobile-launch-android.sh --debug
#   bash apps/mobile/scripts/mobile-launch-android.sh --native
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBUG="${DEBUG:-0}"
NATIVE="${NATIVE:-0}"

for arg in "$@"; do
  case "$arg" in
    --debug) DEBUG=1 ;;
    --native) NATIVE=1 ;;
    -h|--help)
      echo "Usage: $0 [--debug] [--native]"
      exit 0
      ;;
  esac
done

cd "$ROOT"
echo "==> Salareen mobile Android launch (cwd=$PWD)"
bash scripts/mobile-doctor.sh || true

ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
EMULATOR="$ANDROID_HOME/emulator/emulator"
ADB="$ANDROID_HOME/platform-tools/adb"

if [[ ! -x "$EMULATOR" ]]; then
  echo "Android emulator not found at $EMULATOR" >&2
  echo "Set ANDROID_HOME in ~/.zshrc and create an AVD in Android Studio." >&2
  exit 1
fi

if ! "$ADB" devices 2>/dev/null | grep -q "emulator"; then
  AVD="$("$EMULATOR" -list-avds 2>/dev/null | head -n1 || true)"
  if [[ -z "$AVD" ]]; then
    echo "No AVD found. Create one in Android Studio -> Device Manager." >&2
    exit 1
  fi
  echo "==> Booting AVD: $AVD"
  "$EMULATOR" -avd "$AVD" -no-snapshot-load &
  echo "==> Waiting for emulator (up to 120s)…"
  "$ADB" wait-for-device
  for _ in $(seq 1 60); do
    if "$ADB" shell getprop sys.boot_completed 2>/dev/null | grep -q 1; then break; fi
    sleep 2
  done
else
  echo "==> Emulator already running"
fi

export EXPO_NO_TELEMETRY=1
if [[ "$DEBUG" == "1" ]]; then
  export EXPO_DEBUG=1
  export DEBUG=expo:*
  echo "==> Verbose mode: EXPO_DEBUG=1 DEBUG=expo:*"
fi

echo "==> Backend note: Android emulator uses 10.0.2.2 for your Mac (see src/config.ts)"

if [[ "$NATIVE" == "1" ]]; then
  echo "==> Native build: expo run:android"
  if [[ "$DEBUG" == "1" ]]; then
    pnpm exec expo run:android --verbose
  else
    pnpm android
  fi
else
  echo "==> Expo Go path: expo start --android --clear"
  pnpm exec expo start --android --clear
fi
