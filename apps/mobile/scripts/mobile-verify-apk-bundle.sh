#!/usr/bin/env bash
# Guardrail against the recurring Android runtime crash:
#   "Unable to load script. Make sure you're either running Metro ... or that
#    your bundle 'index.android.bundle' is packaged correctly for release."
#
# A standalone (release) APK MUST embed the JS bundle at assets/index.android.bundle.
# If it doesn't, the app can only run against a live Metro dev server, so on a
# real device with no Metro it crashes on launch. This verifies the embed so a
# broken "release" APK fails the build instead of shipping.
#
# Usage: bash scripts/mobile-verify-apk-bundle.sh <path-to-apk>
set -euo pipefail

APK="${1:-}"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  echo "ERROR: APK not found: '$APK'" >&2
  echo "Usage: $0 <path-to-apk>" >&2
  exit 2
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "WARN: unzip not available; cannot verify bundle embed in $APK" >&2
  exit 0
fi

# An APK is a zip; the release JS bundle (plain or Hermes bytecode) lives here.
if unzip -l "$APK" 2>/dev/null | grep -qE 'assets/index\.android\.bundle'; then
  echo "OK: $APK embeds assets/index.android.bundle (standalone — no Metro needed)."
  exit 0
fi

echo "ERROR: $APK does NOT embed assets/index.android.bundle." >&2
echo "This APK will crash on a device with 'Unable to load script' because it" >&2
echo "expects a running Metro dev server. Causes + fixes:" >&2
echo "  - You built a DEBUG apk (assembleDebug / 'expo run:android'). For a" >&2
echo "    standalone device build use: npm run native:build:android:release" >&2
echo "    (assembleRelease embeds the bundle), or an EAS preview/production build." >&2
echo "  - If you intend to run the debug build WITH Metro on a USB device, run:" >&2
echo "    adb reverse tcp:8081 tcp:8081   (then start Metro: npm run dev:android)" >&2
exit 1
