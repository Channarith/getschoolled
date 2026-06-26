#!/usr/bin/env bash
# Launch Salareen mobile on Android emulator with optional verbose Expo logs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBUG="${DEBUG:-1}"
NATIVE="${NATIVE:-0}"
FRESH="${FRESH:-0}"

for arg in "$@"; do
  case "$arg" in
    --debug) DEBUG=1 ;;
    --quiet) DEBUG=0 ;;
    --native) NATIVE=1 ;;
    --fresh) FRESH=1 ;;
    -h|--help)
      echo "Usage: $0 [--quiet] [--fresh] [--native]"
      echo "  (debug is ON by default)"
      exit 0
      ;;
  esac
done

cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$(dirname "$0")/mobile-sim-utils.sh"

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
  for i in $(seq 1 60); do
    if "$ADB" shell getprop sys.boot_completed 2>/dev/null | grep -q 1; then
      echo "    emulator booted (${i} checks)"
      break
    fi
    sleep 2
  done
else
  echo "==> Emulator already running"
fi

bash scripts/mobile-metro-cleanup.sh

export EXPO_NO_TELEMETRY=1
export RCT_METRO_PORT="${RCT_METRO_PORT:-8081}"
if [[ "$DEBUG" == "1" ]]; then
  export EXPO_DEBUG=1
  export DEBUG=expo:*
  echo "==> Verbose mode: EXPO_DEBUG=1 DEBUG=expo:*"
fi

EXPO=(bash scripts/mobile-expo.sh)
EXPO_START_FLAGS=(--port "$RCT_METRO_PORT")
if [[ "$FRESH" == "1" ]]; then
  EXPO_START_FLAGS+=(--clear)
  echo "==> --fresh: clearing Metro cache (slower)"
fi

echo "==> Backend mode: ${MOBILE_DEPLOY_MODE:-cloud} (${MOBILE_CLOUD_BASE_URL:-https://www.salareen.com} when cloud)"
bash scripts/mobile-check-backends.sh || true

if [[ "$NATIVE" == "1" ]]; then
  echo "==> Native build: expo run:android"
  mobile_print_launch_timeline android
  if [[ "$DEBUG" == "1" ]]; then
    "${EXPO[@]}" run:android --verbose
  else
    "${EXPO[@]}" run:android
  fi
else
  echo "==> Expo Go: starting Metro, then opening Android emulator"
  echo "    NOTE: Drive Mode voice (expo-speech-recognition) and driving"
  echo "    detection need a native dev build: npm run launch:android:native"
  echo "    NODE_OPTIONS=$NODE_OPTIONS"
  echo "    Metro port: $RCT_METRO_PORT"
  mobile_prepare_expo_go_launch android "$ADB"
  echo "    EXPO_OFFLINE=1 CI=false (local bundled modules; skip expo.dev hang)"
  mobile_print_launch_timeline android
  echo "==> Starting… (watch for 'Bundled' or 'Opening on Android')"
  "${EXPO[@]}" start --android "${EXPO_START_FLAGS[@]}"
fi
