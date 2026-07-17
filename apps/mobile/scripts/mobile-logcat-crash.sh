#!/usr/bin/env bash
# Capture an Android crash from a connected device/emulator for the Salareen app.
#
# Use this to debug a "crashes on launch / when opening a screen" report (e.g.
# opening a group/solo live class). It streams the logcat lines that matter for a
# React Native crash — the JS stack (ReactNativeJS), the Java fatal exception
# (AndroidRuntime), and native aborts (libc / DEBUG tombstones) — so you can tell
# whether it's a JS error or a native crash and see the stack.
#
# Usage:
#   bash scripts/mobile-logcat-crash.sh            # live stream; reproduce the crash now
#   bash scripts/mobile-logcat-crash.sh --dump     # print the existing buffer and exit
#   SERIAL=emulator-5554 bash scripts/mobile-logcat-crash.sh   # pick a device
#
# Tip: run this, then open the app and trigger the crash. Copy the FATAL/stack
# block into the bug report (or paste it back to the agent).
set -uo pipefail

PKG="com.aiclassroom.app"

ADB="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}/platform-tools/adb"
command -v adb >/dev/null 2>&1 && ADB="adb"
if ! { [ -x "$ADB" ] || command -v "$ADB" >/dev/null 2>&1; }; then
  echo "adb not found. Set ANDROID_HOME (e.g. ~/Library/Android/sdk) or add platform-tools to PATH." >&2
  exit 1
fi

# Pick a device: SERIAL env wins, else the single connected device, else prompt.
SERIAL="${SERIAL:-}"
if [ -z "$SERIAL" ]; then
  mapfile -t _devs < <("$ADB" devices | awk 'NR>1 && $2=="device"{print $1}')
  if [ "${#_devs[@]}" -eq 0 ]; then
    echo "No connected devices/emulators. Plug in a device (USB debugging on) or boot an emulator." >&2
    exit 1
  elif [ "${#_devs[@]}" -eq 1 ]; then
    SERIAL="${_devs[0]}"
  else
    echo "Multiple devices connected; set SERIAL to one of:" >&2
    printf '  %s\n' "${_devs[@]}" >&2
    exit 1
  fi
fi
echo "==> Device: $SERIAL   App: $PKG"

# Grep pattern for the crash-relevant tags/messages.
FILTER='FATAL EXCEPTION|AndroidRuntime|ReactNativeJS|ReactNative|libc|DEBUG|SIGABRT|SIGSEGV|Fatal signal|com.aiclassroom'

if [ "${1:-}" = "--dump" ]; then
  echo "==> Dumping current logcat buffer (crash-relevant lines) ..."
  "$ADB" -s "$SERIAL" logcat -d -v time 2>/dev/null | grep -E "$FILTER" || {
    echo "(no crash-relevant lines found in the buffer)"; exit 0;
  }
  exit 0
fi

echo "==> Clearing old logs, then streaming. Reproduce the crash now (Ctrl-C to stop)."
"$ADB" -s "$SERIAL" logcat -c 2>/dev/null || true
"$ADB" -s "$SERIAL" logcat -v time 2>/dev/null | grep --line-buffered -E "$FILTER"
