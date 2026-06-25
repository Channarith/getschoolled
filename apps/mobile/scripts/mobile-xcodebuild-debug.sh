#!/usr/bin/env bash
# Verbose native iOS build via xcodebuild (bypasses Expo CLI when debugging compile errors).
#
# Prerequisite: ios/ exists (run  pnpm run prebuild  or  pnpm run ios  once).
#
# Usage (from apps/mobile):
#   bash scripts/mobile-xcodebuild-debug.sh
#   SIM_DEVICE="iPhone 16 Pro" bash scripts/mobile-xcodebuild-debug.sh
#   SIM_UDID=A701BBF9-D0E2-41D9-AD2B-3E7E1461E8C9 bash scripts/mobile-xcodebuild-debug.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS builds require macOS." >&2
  exit 1
fi

if [[ ! -d ios ]]; then
  echo "ERROR: apps/mobile/ios/ not found." >&2
  echo "  Generate native projects first:" >&2
  echo "    cd apps/mobile && pnpm run prebuild" >&2
  echo "  Or let Expo create them on first native run:" >&2
  echo "    pnpm run ios:debug" >&2
  exit 1
fi

WS="$(find ios -maxdepth 1 -name '*.xcworkspace' | head -n1)"
if [[ -z "$WS" ]]; then
  echo "ERROR: no .xcworkspace under ios/" >&2
  exit 1
fi

SCHEME="${XCODE_SCHEME:-Salareen}"
if [[ -n "${SIM_UDID:-}" ]]; then
  DEST="id=${SIM_UDID}"
else
  # shellcheck source=mobile-sim-utils.sh
  . "$(dirname "$0")/mobile-sim-utils.sh"
  UDID="$(mobile_ios_pick_simulator)"
  if [[ -z "$UDID" ]]; then
    echo "ERROR: no bootable simulator for SIM_DEVICE=${SIM_DEVICE:-iPhone 16}" >&2
    echo "  Install a runtime: Xcode → Settings → Platforms → iOS Simulator" >&2
    echo "  List devices: xcrun simctl list devices available" >&2
    exit 1
  fi
  DEST="id=${UDID}"
fi

echo "==> xcodebuild debug (verbose)"
echo "    workspace: $WS"
echo "    scheme:    $SCHEME"
echo "    dest:      $DEST"
echo ""

/Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild \
  -workspace "$WS" \
  -configuration Debug \
  -scheme "$SCHEME" \
  -destination "$DEST" \
  build
