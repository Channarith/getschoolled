#!/usr/bin/env bash
# Shared simulator boot helpers for mobile launch scripts.

mobile_ios_pick_simulator() {
  local name="${SIM_DEVICE:-iPhone 16}"
  xcrun simctl list devices available 2>/dev/null \
    | grep -F "${name} (" \
    | head -n1 \
    | sed -E 's/.*\(([0-9A-F-]{36})\).*/\1/'
}

mobile_ios_boot_simulator() {
  local udid
  udid="$(mobile_ios_pick_simulator)"
  if [[ -z "$udid" ]]; then
    echo "WARN: no iOS simulator matching SIM_DEVICE=${SIM_DEVICE:-iPhone 16}" >&2
    open -a Simulator || true
    return 0
  fi
  echo "==> Booting iOS Simulator (${SIM_DEVICE:-iPhone 16}, $udid)"
  xcrun simctl boot "$udid" 2>/dev/null || true
  open -a Simulator || true
  echo "    waiting for simulator to finish booting…"
  xcrun simctl bootstatus "$udid" -b 2>/dev/null || sleep 3
  echo "    simulator ready"
}

mobile_print_launch_timeline() {
  local platform="$1"
  echo ""
  echo "==> What to expect (first launch can be slow — this is normal)"
  echo "    0:00–2:00   Metro starts (may show little output)"
  echo "    2:00–4:00   First JS bundle build (735 modules) — still working if silent"
  if [[ "$platform" == "ios" ]]; then
    echo "    4:00+       Expo Go opens in Simulator with Salareen"
  else
    echo "    4:00+       Expo Go opens on the Android emulator"
  fi
  echo "    Tip: leave this terminal open — Metro must keep running"
  echo "    Stuck 5+ min? Ctrl+C, then: bash scripts/mobile-launch-${platform}.sh --debug"
  echo ""
}
