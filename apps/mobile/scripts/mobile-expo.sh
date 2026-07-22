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

# Auto-offline when expo.dev is unreachable (corporate proxy / sandbox returns
# "Blocked by…" and Expo crashes with SyntaxError on JSON.parse). Launch scripts
# already set EXPO_OFFLINE=1; this covers bare `mobile-expo.sh start`.
if [ -z "${EXPO_OFFLINE:-}" ]; then
  if ! curl -fsS --max-time 2 "https://expo.dev" >/dev/null 2>&1; then
    export EXPO_OFFLINE=1
    echo "==> EXPO_OFFLINE=1 (expo.dev unreachable — skip native-module version fetch)"
  fi
fi

# Only wipe Metro cache when the caller asked for a clean start. Unconditional
# clears made every `start` a 30–90s cold rebuild. Expo's own --clear still
# clears transform cache; we also drop our on-disk metro dirs to match.
_clear_metro=0
for _arg in "$@"; do
  if [ "$_arg" = "--clear" ] || [ "$_arg" = "-c" ]; then
    _clear_metro=1
    break
  fi
done
if [ "$_clear_metro" -eq 1 ]; then
  echo "==> Clearing Metro cache (requested via --clear)"
  rm -rf node_modules/.cache/metro .expo/metro 2>/dev/null || true
fi

# `expo prebuild --clean` deletes+regenerates native dirs, but its own rmdir can
# fail with "ENOTEMPTY: directory not empty, rmdir '.../android/app'" when a
# leftover build artifact blocks the non-recursive delete. Pre-clean the target
# native dir(s) ourselves (recursive + retry) so prebuild starts fresh.
if [[ "${1:-}" == "prebuild" ]] && printf '%s\n' "$@" | grep -qx -- "--clean"; then
  _clean_targets=""
  case " $* " in
    *" --platform ios "*) _clean_targets="ios" ;;
    *" --platform android "*) _clean_targets="android" ;;
    *) _clean_targets="android ios" ;;
  esac
  # shellcheck disable=SC2086
  node scripts/clean-native-dirs.js $_clean_targets || true
fi

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

# For `start` (dev server), clear zombie listeners on the target port first so
# we don't attach to a hung Metro that returns empty replies.
if [[ "${1:-}" == "start" ]]; then
  _start_port="${RCT_METRO_PORT:-8081}"
  _prev=""
  for _arg in "$@"; do
    if [ "$_prev" = "--port" ]; then
      _start_port="$_arg"
      break
    fi
    _prev="$_arg"
  done
  MOBILE_METRO_PORTS="$_start_port" bash scripts/mobile-metro-cleanup.sh >/dev/null 2>&1 || true
fi

if [ -e node_modules/.bin/expo ]; then
  exec node_modules/.bin/expo "$@"
fi
if [ -f node_modules/expo/bin/cli ]; then
  exec node node_modules/expo/bin/cli "$@"
fi

echo "ERROR: expo not installed — run: bash scripts/mobile-install.sh" >&2
exit 1
