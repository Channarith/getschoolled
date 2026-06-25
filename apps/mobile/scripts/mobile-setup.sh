#!/usr/bin/env bash
# First-time Salareen mobile setup: deps, doctor, Expo Go, launch instructions.
#
# Run once on a new Mac before daily dev:
#   cd apps/mobile
#   bash scripts/mobile-setup.sh
#
# Options:
#   --ios-only       Skip Android Expo Go install
#   --android-only   Skip iOS Expo Go install (non-macOS)
#   --skip-expo-go   Only install npm deps + doctor
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(dirname "$0")"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$SCRIPT_DIR/mobile-env.sh"
# shellcheck source=mobile-expo-go-utils.sh
. "$SCRIPT_DIR/mobile-expo-go-utils.sh"

SETUP_IOS=1
SETUP_ANDROID=1
SKIP_EXPO_GO=0

for arg in "$@"; do
  case "$arg" in
    --ios-only) SETUP_ANDROID=0 ;;
    --android-only) SETUP_IOS=0 ;;
    --skip-expo-go) SKIP_EXPO_GO=1 ;;
    -h|--help)
      echo "Usage: $0 [--ios-only] [--android-only] [--skip-expo-go]"
      exit 0
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  SETUP_IOS=0
fi

echo "=========================================="
echo " Salareen mobile — FIRST-TIME SETUP"
echo "=========================================="
echo ""
echo "This wizard installs dependencies, checks your environment, and"
echo "installs Expo Go on the simulator/emulator (network required once)."
echo ""
mobile_print_expo_go_notes
echo ""

echo "==> Step 1/4: Install npm dependencies"
if ! bash "$SCRIPT_DIR/mobile-install.sh"; then
  echo "FAIL: dependency install failed" >&2
  exit 1
fi
echo ""

echo "==> Step 2/4: Environment doctor"
if ! bash "$SCRIPT_DIR/mobile-doctor.sh"; then
  echo ""
  echo "FAIL: fix doctor FAIL items above, then re-run: bash scripts/mobile-setup.sh" >&2
  exit 1
fi
echo ""

if [[ "$SKIP_EXPO_GO" == "1" ]]; then
  echo "==> Skipping Expo Go install (--skip-expo-go)"
else
  echo "==> Step 3/4: Install Expo Go (one-time, needs network)"
  SDK="$(mobile_expo_sdk_version)"
  echo "    Project SDK: ${SDK}"
  echo ""

  if [[ "$SETUP_IOS" == "1" ]]; then
  # shellcheck source=mobile-sim-utils.sh
    . "$SCRIPT_DIR/mobile-sim-utils.sh"
    if mobile_ios_expo_go_installed; then
      echo "  OK   iOS: Expo Go already on simulator"
    else
      echo "  …    iOS: downloading Expo Go for SDK ${SDK}…"
      bash "$SCRIPT_DIR/mobile-install-expo-go-ios.sh"
    fi
  fi

  if [[ "$SETUP_ANDROID" == "1" ]]; then
    ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
  # shellcheck source=mobile-sim-utils.sh
    . "$SCRIPT_DIR/mobile-sim-utils.sh"
    ADB="$ANDROID_HOME/platform-tools/adb"
    if [[ -x "$ADB" ]] && "$ADB" devices 2>/dev/null | grep -q "emulator"; then
      if mobile_android_expo_go_installed "$ADB"; then
        echo "  OK   Android: Expo Go already on emulator"
      else
        echo "  …    Android: installing Expo Go…"
        bash "$SCRIPT_DIR/mobile-install-expo-go-android.sh" || true
      fi
    else
      echo "  SKIP Android Expo Go — boot an emulator first, then run:"
      echo "       bash scripts/mobile-install-expo-go-android.sh"
    fi
  fi
  echo ""
fi

echo "==> Step 4/4: Verify Expo Go + Orbit status"
# shellcheck source=mobile-sim-utils.sh
. "$SCRIPT_DIR/mobile-sim-utils.sh"
if [[ "$SETUP_IOS" == "1" ]]; then
  if mobile_ios_expo_go_installed; then
    echo "  OK   Expo Go on iOS Simulator"
  else
    echo "  FAIL Expo Go missing on iOS — run: bash scripts/mobile-install-expo-go-ios.sh" >&2
    exit 1
  fi
  if mobile_expo_go_ios_cache_present; then
    echo "  OK   Expo Go cache: $(mobile_expo_go_ios_cache_dir)"
  else
    echo "  WARN Expo Go cache empty (install may re-download next time)"
  fi
fi
if mobile_expo_orbit_installed; then
  echo "  OK   Expo Orbit installed (optional — not required for daily dev)"
else
  echo "  INFO Expo Orbit not installed (optional — https://expo.dev/orbit)"
fi
echo ""

echo "=========================================="
echo " SETUP COMPLETE — daily dev commands"
echo "=========================================="
echo ""
if [[ "$SETUP_IOS" == "1" ]]; then
  echo "  iOS Simulator:"
  echo "    bash scripts/mobile-launch-ios.sh"
  echo "    pnpm run launch:ios"
fi
if [[ "$SETUP_ANDROID" == "1" ]]; then
  echo "  Android emulator (boot AVD first):"
  echo "    bash scripts/mobile-launch-android.sh"
  echo "    pnpm run launch:android"
fi
echo ""
echo "  Backend (separate terminal, from repo root):"
echo "    cd services/curriculum && DEPLOY_MODE=local PYTHONPATH=src \\"
echo "      uvicorn curriculum.main:app --port 8005"
echo ""
echo "  Troubleshooting: bash scripts/mobile-doctor.sh"
echo "                   VERBOSE=1 bash scripts/mobile-doctor.sh"
echo ""
