#!/usr/bin/env bash
# Release .xcarchive for physical iOS devices (no EAS).
#
# Produces: apps/mobile/ios/build/Salareen.xcarchive
# Export IPA: open the archive in Xcode → Window → Organizer → Distribute App
#   (Ad Hoc / Development / App Store per your provisioning).
#
# Prerequisites:
#   - macOS + Xcode + CocoaPods
#   - Apple Developer account; signing team set in Xcode for com.aiclassroom.app
#   - apps/mobile deps installed (bash scripts/mobile-install.sh)
#
# Usage (from apps/mobile):
#   bash scripts/mobile-xcodebuild-release.sh
#   DEVELOPMENT_TEAM=ABCDE12345 bash scripts/mobile-xcodebuild-release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MOBILE_ROOT="$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-deps.sh
. "$(dirname "$0")/mobile-deps.sh"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "iOS release builds require macOS." >&2
  exit 1
fi

if ! mobile_deps_has_expo; then
  echo "ERROR: expo missing — bash scripts/mobile-install.sh" >&2
  exit 1
fi

if [[ ! -d ios ]]; then
  echo "==> ios/ missing — running expo prebuild (one-time)"
  bash scripts/mobile-expo.sh prebuild --platform ios --no-install
fi

bash scripts/mobile-ios-pod-refresh.sh

if [[ ! -d node_modules/expo-asset ]]; then
  echo "ERROR: expo-asset missing — run: pnpm install" >&2
  exit 1
fi

WS="$(find ios -maxdepth 1 -name '*.xcworkspace' | head -n1)"
if [[ -z "$WS" ]]; then
  echo "ERROR: no .xcworkspace under ios/" >&2
  exit 1
fi

SCHEME="${XCODE_SCHEME:-Salareen}"
ARCHIVE_PATH="${ARCHIVE_PATH:-$ROOT/ios/build/Salareen.xcarchive}"
mkdir -p "$(dirname "$ARCHIVE_PATH")"

XCODE_ARGS=(
  -workspace "$WS"
  -scheme "$SCHEME"
  -configuration Release
  -destination "generic/platform=iOS"
  -archivePath "$ARCHIVE_PATH"
  archive
)

if [[ -n "${DEVELOPMENT_TEAM:-}" ]]; then
  XCODE_ARGS+=(DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM")
  XCODE_ARGS+=(CODE_SIGN_STYLE=Automatic)
fi

echo "==> xcodebuild release archive (physical device, no EAS)"
echo "    workspace: $WS"
echo "    scheme:    $SCHEME"
echo "    archive:   $ARCHIVE_PATH"
echo ""
echo "    After archive succeeds:"
echo "      open $ARCHIVE_PATH"
echo "    Or: Xcode → Window → Organizer → Distribute App"
echo ""

/Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild "${XCODE_ARGS[@]}"

echo ""
echo "OK archive -> $ARCHIVE_PATH"
echo "Next: Xcode Organizer → Distribute App → Ad Hoc (registered devices) or App Store / TestFlight"
