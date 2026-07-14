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

BUNDLE="assets/index.android.bundle"

# Inspect the APK (a zip) for the embedded bundle. IMPORTANT: macOS's Info-ZIP
# `unzip` frequently mis-parses APKs (the APK Signature Scheme v2/v3 block and
# zip64 records) and lists NO entries — a false "not embedded". Python's zipfile
# reads the zip central directory correctly, so prefer it; fall back to
# unzip/jar only when python3 is unavailable.
#   Prints: present | absent | unknown
detect() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - "$APK" "$BUNDLE" <<'PY' 2>/dev/null || echo unknown
import sys, zipfile
apk, target = sys.argv[1], sys.argv[2]
try:
    with zipfile.ZipFile(apk) as z:
        names = set(z.namelist())
except Exception:
    print("unknown"); sys.exit(0)
# The release bundle (plain JS or Hermes bytecode) is at assets/index.android.bundle.
print("present" if target in names else "absent")
PY
    return 0
  fi
  if command -v unzip >/dev/null 2>&1 && unzip -l "$APK" 2>/dev/null | grep -qE 'assets/index\.android\.bundle'; then
    echo present; return 0
  fi
  if command -v jar >/dev/null 2>&1 && jar tf "$APK" 2>/dev/null | grep -qE 'assets/index\.android\.bundle'; then
    echo present; return 0
  fi
  echo unknown
}

STATUS="$(detect | tail -n1)"

case "$STATUS" in
  present)
    echo "OK: $APK embeds $BUNDLE (standalone — no Metro needed)."
    exit 0
    ;;
  absent)
    echo "ERROR: $APK does NOT embed $BUNDLE." >&2
    echo "This APK will crash on a device with 'Unable to load script' because it" >&2
    echo "expects a running Metro dev server. Causes + fixes:" >&2
    echo "  - You built a DEBUG apk (assembleDebug / 'expo run:android'). For a" >&2
    echo "    standalone device build use: npm run native:build:android:release" >&2
    echo "    (assembleRelease embeds the bundle), or an EAS preview/production build." >&2
    echo "  - If you intend to run the debug build WITH Metro on a USB device, run:" >&2
    echo "    adb reverse tcp:8081 tcp:8081   (then start Metro: npm run dev:android)" >&2
    exit 1
    ;;
  *)
    # Couldn't read the APK's entries (no python3, and unzip/jar unavailable or
    # unable to parse). Don't fail an otherwise-successful build on a tooling gap.
    echo "WARN: could not read $APK to verify the embedded bundle (no working" >&2
    echo "      python3/unzip/jar). Skipping the embed check — install python3 to" >&2
    echo "      enable it. Verify manually: python3 -c \"import zipfile;print('$BUNDLE' in zipfile.ZipFile('$APK').namelist())\"" >&2
    exit 0
    ;;
esac
