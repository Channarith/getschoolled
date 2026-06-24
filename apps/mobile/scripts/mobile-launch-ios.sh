#!/usr/bin/env bash
# Launch Salareen mobile on iOS Simulator with optional verbose Expo logs.
# Usage (from anywhere):
#   bash apps/mobile/scripts/mobile-launch-ios.sh
#   bash apps/mobile/scripts/mobile-launch-ios.sh --debug
#   bash apps/mobile/scripts/mobile-launch-ios.sh --native   # expo run:ios (slow)
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
      echo "  --debug   EXPO_DEBUG=1 + Metro verbose"
      echo "  --native  expo run:ios (native compile, not Expo Go)"
      exit 0
      ;;
  esac
done

cd "$ROOT"
echo "==> Salareen mobile iOS launch (cwd=$PWD)"
pnpm run doctor || true

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS Simulator requires macOS." >&2
  exit 1
fi

echo "==> Opening Simulator (if not already running)"
open -a Simulator || true
sleep 2

export EXPO_NO_TELEMETRY=1
if [[ "$DEBUG" == "1" ]]; then
  export EXPO_DEBUG=1
  export DEBUG=expo:*
  echo "==> Verbose mode: EXPO_DEBUG=1 DEBUG=expo:*"
fi

if [[ "$NATIVE" == "1" ]]; then
  echo "==> Native build: expo run:ios (first run can take 10–20 min)"
  if [[ "$DEBUG" == "1" ]]; then
    pnpm exec expo run:ios --verbose
  else
    pnpm ios
  fi
else
  echo "==> Expo Go path: expo start --ios --clear"
  pnpm exec expo start --ios --clear
fi
