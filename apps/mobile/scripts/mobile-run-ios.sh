#!/usr/bin/env bash
# Native iOS build (expo run:ios) with a simulator runtime compatible with Xcode.
# Boots a 26.x simulator by default — avoids error 70 when an older iOS 18.x sim is booted.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$(dirname "$0")/mobile-sim-utils.sh"

export SIM_DEVICE="${SIM_DEVICE:-iPhone 17}"
export SIM_RUNTIME="${SIM_RUNTIME:-26.4}"

bash scripts/mobile-ios-pod-refresh.sh

udid="$(mobile_ios_pick_simulator)"
if [[ -z "$udid" ]]; then
  echo "ERROR: no simulator for SIM_DEVICE=${SIM_DEVICE} SIM_RUNTIME=${SIM_RUNTIME}" >&2
  echo "  List: xcrun simctl list devices available" >&2
  echo "  Override: SIM_DEVICE='iPhone 17 Pro' SIM_RUNTIME=26.4 npm run ios" >&2
  exit 1
fi

echo "==> Native iOS build → ${SIM_DEVICE} (runtime iOS ${SIM_RUNTIME}, $udid)"
xcrun simctl boot "$udid" 2>/dev/null || true
open -a Simulator 2>/dev/null || true
xcrun simctl bootstatus "$udid" -b 2>/dev/null || sleep 2

exec bash scripts/mobile-expo.sh run:ios --device "$udid" "$@"
