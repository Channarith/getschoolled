#!/usr/bin/env bash
# Launch Salareen mobile on iOS Simulator with optional verbose Expo logs.
# Usage (from anywhere):
#   bash apps/mobile/scripts/mobile-launch-ios.sh
#   bash scripts/mobile-launch-ios.sh --debug
#   bash apps/mobile/scripts/mobile-launch-ios.sh --fresh   # clear Metro cache
#   bash apps/mobile/scripts/mobile-launch-ios.sh --native   # expo run:ios (10–20 min)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEBUG="${DEBUG:-0}"
NATIVE="${NATIVE:-0}"
FRESH="${FRESH:-0}"

for arg in "$@"; do
  case "$arg" in
    --debug) DEBUG=1 ;;
    --native) NATIVE=1 ;;
    --fresh) FRESH=1 ;;
    -h|--help)
      echo "Usage: $0 [--debug] [--fresh] [--native]"
      echo "  --debug   EXPO_DEBUG=1 + Metro verbose"
      echo "  --fresh   expo start --clear (slow; only if Metro cache is corrupt)"
      echo "  --native  expo run:ios (native compile, not Expo Go)"
      exit 0
      ;;
  esac
done

cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$(dirname "$0")/mobile-sim-utils.sh"

echo "==> Salareen mobile iOS launch (cwd=$PWD)"
bash scripts/mobile-doctor.sh || true

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS Simulator requires macOS." >&2
  exit 1
fi

mobile_ios_boot_simulator

bash scripts/mobile-metro-cleanup.sh

export EXPO_NO_TELEMETRY=1
export RCT_METRO_PORT="${RCT_METRO_PORT:-8081}"
if [[ "$DEBUG" == "1" ]]; then
  export EXPO_DEBUG=1
  export DEBUG=expo:*
  echo "==> Verbose mode: EXPO_DEBUG=1 DEBUG=expo:*"
fi

EXPO=(bash scripts/mobile-expo.sh)
EXPO_START_FLAGS=(--port "$RCT_METRO_PORT" --localhost)
if [[ "$FRESH" == "1" ]]; then
  EXPO_START_FLAGS+=(--clear)
  echo "==> --fresh: clearing Metro cache (slower)"
fi

if [[ "$NATIVE" == "1" ]]; then
  echo "==> Native build: expo run:ios (first run can take 10–20 min)"
  mobile_print_launch_timeline ios
  if [[ "$DEBUG" == "1" ]]; then
    "${EXPO[@]}" run:ios --verbose
  else
    "${EXPO[@]}" run:ios
  fi
else
  echo "==> Expo Go: starting Metro, then opening iOS Simulator"
  echo "    NODE_OPTIONS=$NODE_OPTIONS"
  echo "    Metro port: $RCT_METRO_PORT (localhost)"
  mobile_configure_expo_offline ios
  if [[ "${EXPO_OFFLINE:-0}" == "1" ]]; then
    echo "    EXPO_OFFLINE=1 CI=$CI (Expo Go installed; skip expo.dev fetch)"
  else
    echo "    EXPO_OFFLINE unset CI=$CI (first launch installs Expo Go — allow network)"
  fi
  mobile_print_launch_timeline ios
  echo "==> Starting… (watch for 'Bundled' or 'Opening on iOS')"
  "${EXPO[@]}" start --ios "${EXPO_START_FLAGS[@]}"
fi
