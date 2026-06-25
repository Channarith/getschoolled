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

mobile_ios_expo_go_installed() {
  xcrun simctl listapps booted 2>/dev/null | grep -q "host.exp.Exponent" && return 0
  local udid
  udid="$(mobile_ios_pick_simulator)"
  if [[ -n "$udid" ]]; then
    xcrun simctl listapps "$udid" 2>/dev/null | grep -q "host.exp.Exponent" && return 0
  fi
  return 1
}

mobile_android_expo_go_installed() {
  local adb="${1:-}"
  if [[ -z "$adb" || ! -x "$adb" ]]; then
    return 1
  fi
  "$adb" shell pm list packages 2>/dev/null | grep -q "host.exp.exponent" && return 0
  return 1
}

# Enable EXPO_OFFLINE when Expo Go is present (avoids expo.dev fetch hang). Leave
# offline off on first launch so Expo can auto-install Expo Go (needs network once).
mobile_configure_expo_offline() {
  local platform="$1"
  local adb="${2:-}"

  if [[ -n "${EXPO_OFFLINE:-}" ]]; then
    if [[ "${EXPO_OFFLINE}" == "1" ]]; then
      if [[ "$platform" == "ios" ]] && ! mobile_ios_expo_go_installed; then
        echo "WARN: EXPO_OFFLINE=1 but Expo Go is not on the iOS simulator." >&2
        echo "      Clearing offline mode so Expo can install Expo Go (needs network)." >&2
        unset EXPO_OFFLINE
      elif [[ "$platform" == "android" ]] && ! mobile_android_expo_go_installed "$adb"; then
        echo "WARN: EXPO_OFFLINE=1 but Expo Go is not on the Android emulator." >&2
        echo "      Clearing offline mode so Expo can install Expo Go (needs network)." >&2
        unset EXPO_OFFLINE
      fi
    fi
    return 0
  fi

  if [[ "$platform" == "ios" ]]; then
    if mobile_ios_expo_go_installed; then
      export EXPO_OFFLINE=1
    else
      unset EXPO_OFFLINE || true
    fi
  elif [[ "$platform" == "android" ]]; then
    if mobile_android_expo_go_installed "$adb"; then
      export EXPO_OFFLINE=1
    else
      unset EXPO_OFFLINE || true
    fi
  fi
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
