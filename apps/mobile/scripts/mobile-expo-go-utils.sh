#!/usr/bin/env bash
# Shared Expo Go / Orbit helpers for doctor, setup, and launch scripts.

mobile_expo_home_dir() {
  echo "${EXPO_HOME:-$HOME/.expo}"
}

mobile_expo_sdk_version() {
  node -e "
    const path = require('path');
    const root = path.join('$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)');
    const { getExpoSDKVersion } = require('@expo/config/build/getExpoSDKVersion');
    process.stdout.write(getExpoSDKVersion(root));
  " 2>/dev/null || echo "unknown"
}

mobile_expo_go_ios_cache_dir() {
  echo "$(mobile_expo_home_dir)/ios-simulator-app-cache"
}

mobile_expo_go_android_cache_dir() {
  echo "$(mobile_expo_home_dir)/android-apk-cache"
}

mobile_expo_orbit_installed() {
  command -v orbit >/dev/null 2>&1 && return 0
  [ -d "/Applications/Expo Orbit.app" ] && return 0
  return 1
}

mobile_expo_go_ios_cache_present() {
  local cache
  cache="$(mobile_expo_go_ios_cache_dir)"
  [ -d "$cache" ] && find "$cache" -maxdepth 1 -name '*.app' -type d 2>/dev/null | grep -q .
}

mobile_expo_go_android_cache_present() {
  local cache
  cache="$(mobile_expo_go_android_cache_dir)"
  [ -d "$cache" ] && find "$cache" -maxdepth 1 -name '*.apk' -type f 2>/dev/null | grep -q .
}

mobile_print_expo_go_notes() {
  echo "  Expo Go vs Expo Orbit:"
  echo "    • Expo Go  = the app that runs your JS on simulator/phone (REQUIRED for Path A)."
  echo "    • Expo Orbit = optional desktop helper for installs/dev builds (NOT required)."
  echo "  First-time install (network once):"
  echo "    bash scripts/mobile-setup.sh"
  echo "  Or platform-only:"
  echo "    bash scripts/mobile-install-expo-go-ios.sh"
  echo "    bash scripts/mobile-install-expo-go-android.sh"
}
