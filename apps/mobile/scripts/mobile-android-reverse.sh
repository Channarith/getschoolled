#!/usr/bin/env bash
# Recovery for the Android "Unable to load script / index.android.bundle" red
# screen on a DEBUG/dev build: point every connected device's localhost:8081 at
# the host's Metro (adb reverse), then remind you to start Metro and tap Reload.
#
# Usage (from apps/mobile):  bash scripts/mobile-android-reverse.sh
#   then:  pnpm start        # (if Metro isn't already running)
#   then:  on the device, tap RELOAD (or press R twice)
#
# For a self-contained app that needs NO Metro, build a release APK instead:
#   pnpm run native:build:android:release   (JS bundle embedded)
set -euo pipefail

PORT="${RCT_METRO_PORT:-8081}"
ADB="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}/platform-tools/adb"
command -v adb >/dev/null 2>&1 && ADB="adb"

if ! { [[ -x "$ADB" ]] || command -v "$ADB" >/dev/null 2>&1; }; then
  echo "adb not found. Set ANDROID_HOME (e.g. ~/Library/Android/sdk) or add platform-tools to PATH." >&2
  exit 1
fi

mapfile -t DEVICES < <("$ADB" devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1}')
if [[ ${#DEVICES[@]} -eq 0 ]]; then
  echo "No connected devices/emulators. Plug in a device (USB debugging on) or boot an emulator, then re-run." >&2
  exit 1
fi

for s in "${DEVICES[@]}"; do
  if "$ADB" -s "$s" reverse "tcp:$PORT" "tcp:$PORT" >/dev/null 2>&1; then
    echo "OK  adb reverse tcp:$PORT -> host Metro for $s"
  else
    echo "!!  could not set adb reverse for $s" >&2
  fi
done

echo ""
echo "Next:"
echo "  1) Make sure Metro is running:  pnpm start   (port $PORT)"
echo "  2) On the device, tap RELOAD (or press R twice) on the red screen."
echo "If it still can't load, install a self-contained release APK instead:"
echo "  pnpm run native:build:android:release"
