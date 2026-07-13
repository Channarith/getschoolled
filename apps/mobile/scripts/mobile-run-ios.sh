#!/usr/bin/env bash
# Native iOS build (expo run:ios) — simulator (default) or plugged-in physical iPhone.
#
# Simulator (default):
#   bash scripts/mobile-run-ios.sh
#   SIM_DEVICE='iPhone 17' SIM_RUNTIME=26.4 bash scripts/mobile-run-ios.sh
#
# Physical device (USB; enable Signing in Xcode first):
#   bash scripts/mobile-run-ios.sh --physical
#   bash scripts/mobile-run-ios.sh --device          # same (Expo picks connected iPhone)
#   bash scripts/mobile-run-ios.sh --device <UDID>   # specific device
#   USE_PHYSICAL_DEVICE=1 bash scripts/mobile-run-ios.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-sim-utils.sh
. "$(dirname "$0")/mobile-sim-utils.sh"

bash scripts/mobile-ios-pod-refresh.sh

use_physical="${USE_PHYSICAL_DEVICE:-0}"
expo_args=()
skip_next=0

for ((i = 1; i <= $#; i++)); do
  if [[ "$skip_next" == "1" ]]; then
    skip_next=0
    continue
  fi
  arg="${!i}"
  case "$arg" in
    --physical)
      use_physical=1
      ;;
    --device)
      next_i=$((i + 1))
      if [[ $next_i -gt $# ]]; then
        use_physical=1
      else
        next_arg="${!next_i}"
        if [[ "$next_arg" == --* ]]; then
          use_physical=1
        else
          use_physical=1
          expo_args+=("--device" "$next_arg")
          skip_next=1
        fi
      fi
      ;;
    *)
      expo_args+=("$arg")
      ;;
  esac
done

if [[ "$use_physical" == "1" ]]; then
  echo "==> Native iOS build → physical device (plug in iPhone, trust this Mac, signing enabled in Xcode)"
  echo "    List devices: xcrun xctrace list devices"
  if [[ ${#expo_args[@]} -eq 0 ]]; then
    exec bash scripts/mobile-expo.sh run:ios --device
  fi
  exec bash scripts/mobile-expo.sh run:ios "${expo_args[@]}"
fi

export SIM_DEVICE="${SIM_DEVICE:-iPhone 17}"
export SIM_RUNTIME="${SIM_RUNTIME:-26.4}"

udid="$(mobile_ios_pick_simulator)"
if [[ -z "$udid" ]]; then
  echo "ERROR: no simulator for SIM_DEVICE=${SIM_DEVICE} SIM_RUNTIME=${SIM_RUNTIME}" >&2
  echo "  List: xcrun simctl list devices available" >&2
  echo "  Physical iPhone instead: pnpm run ios:device" >&2
  exit 1
fi

echo "==> Native iOS build → ${SIM_DEVICE} (runtime iOS ${SIM_RUNTIME}, $udid)"
xcrun simctl boot "$udid" 2>/dev/null || true
open -a Simulator 2>/dev/null || true
xcrun simctl bootstatus "$udid" -b 2>/dev/null || sleep 2

exec bash scripts/mobile-expo.sh run:ios --device "$udid" "${expo_args[@]}"
