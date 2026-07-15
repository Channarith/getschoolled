#!/usr/bin/env bash
# Run Expo CLI directly (no pnpm exec) with heap headroom for Metro.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-deps.sh
MOBILE_ROOT="$ROOT"
. "$(dirname "$0")/mobile-deps.sh"

mobile_deps_ensure_metro_local || exit 1

# Stale Metro cache can 500 after materializing symlinked deps.
rm -rf node_modules/.cache/metro .expo/metro 2>/dev/null || true

# Native Android: patch settings.gradle before Gradle runs so @react-native/gradle-plugin
# resolves only under apps/mobile/node_modules (avoids duplicate :gradle-plugin when
# ~/node_modules/.pnpm also exists on the developer machine).
if [[ "${1:-}" == "run:android" ]] && [[ -d android ]]; then
  node scripts/patch-gradle-wrapper.js
fi

# Metro reachability guard for run:android. A debug build loads
# index.android.bundle from Metro; a USB-connected PHYSICAL device can't reach
# the host's localhost:8081 without a reverse tunnel and crashes on launch with
# "Unable to load script". `expo run:android` sets this during its own launch,
# but we also set it here for every connected device (idempotent, harmless for
# emulators) so reopening the installed app / reconnecting keeps Metro reachable.
# For a self-contained install that needs NO Metro use native:build:android:release.
if [[ "${1:-}" == "run:android" ]]; then
  _adb="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}/platform-tools/adb"
  command -v adb >/dev/null 2>&1 && _adb="adb"
  if [[ -x "$_adb" ]] || command -v "$_adb" >/dev/null 2>&1; then
    for _s in $("$_adb" devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1}'); do
      "$_adb" -s "$_s" reverse "tcp:${RCT_METRO_PORT:-8081}" "tcp:${RCT_METRO_PORT:-8081}" >/dev/null 2>&1 \
        && echo "==> adb reverse tcp:${RCT_METRO_PORT:-8081} set for $_s (Metro reachable on device)" || true
    done
  fi
fi

if [[ "${1:-}" == "run:ios" ]] && [[ -d ios ]]; then
  bash scripts/mobile-ios-pod-refresh.sh
fi

if [ -e node_modules/.bin/expo ]; then
  exec node_modules/.bin/expo "$@"
fi
if [ -f node_modules/expo/bin/cli ]; then
  exec node node_modules/expo/bin/cli "$@"
fi

echo "ERROR: expo not installed — run: bash scripts/mobile-install.sh" >&2
exit 1
