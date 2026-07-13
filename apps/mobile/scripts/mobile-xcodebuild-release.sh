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
#
# One-time: log into Xcode with your Apple ID (Xcode → Settings → Accounts).
# If archive fails with "No profiles found", open ios/*.xcworkspace → Salareen target
# → Signing & Capabilities → enable "Automatically manage signing" and pick Team.
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

# Always regenerate the native iOS project from app.json so Info.plist
# (privacy usage strings, version, build number) can never drift from the
# Expo config. Set KEEP_IOS=1 to skip (fast rebuild during local iteration).
# A stale native project is exactly how App Store validation 90683 (missing
# NSPhotoLibraryUsageDescription) slips through: the archive is built from an
# out-of-date Info.plist that predates the app.json fix.
if [[ "${KEEP_IOS:-0}" == "1" && -d ios ]]; then
  echo "==> KEEP_IOS=1 — reusing existing ios/ (Info.plist NOT regenerated)"
else
  echo "==> Regenerating native ios/ from app.json (expo prebuild --clean)"
  bash scripts/mobile-expo.sh prebuild --platform ios --no-install --clean
fi

# Fresh build: drop any previous archive/artifacts so we never ship a cached,
# stale binary (per release policy: always a fresh build, versioned output).
if [[ -d ios/build ]]; then
  echo "==> Removing stale ios/build artifacts for a clean archive"
  rm -rf ios/build
fi

bash scripts/mobile-ios-pod-refresh.sh

# Guard: the archive MUST carry the photo-library purpose strings, or Apple
# rejects the upload with error 90683. Fail early with a clear message rather
# than after a long archive + upload round-trip.
PLIST="ios/Salareen/Info.plist"
if [[ -f "$PLIST" ]]; then
  for key in NSPhotoLibraryUsageDescription NSPhotoLibraryAddUsageDescription; do
    if ! /usr/libexec/PlistBuddy -c "Print :$key" "$PLIST" >/dev/null 2>&1; then
      echo "ERROR: $key missing from $PLIST after prebuild." >&2
      echo "       Check apps/mobile/app.json expo.ios.infoPlist." >&2
      exit 1
    fi
  done
  echo "==> Verified NSPhotoLibrary purpose strings present in Info.plist"
fi

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

# Resolve Apple Developer team (required for device/archive signing).
if [[ -z "${DEVELOPMENT_TEAM:-}" ]]; then
  DEVELOPMENT_TEAM="$(
    /Applications/Xcode.app/Contents/Developer/usr/bin/xcodebuild \
      -workspace "$WS" \
      -scheme "$SCHEME" \
      -configuration Release \
      -showBuildSettings 2>/dev/null \
      | awk -F' = ' '/^[[:space:]]*DEVELOPMENT_TEAM = / { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit }'
  )"
fi
DEVELOPMENT_TEAM="${DEVELOPMENT_TEAM// /}"

if [[ -z "$DEVELOPMENT_TEAM" ]]; then
  echo "ERROR: No DEVELOPMENT_TEAM for com.aiclassroom.app." >&2
  echo "" >&2
  echo "  Fix (pick one):" >&2
  echo "    1. Open ios/*.xcworkspace in Xcode → Salareen target → Signing & Capabilities" >&2
  echo "       → check 'Automatically manage signing' → select your Team → close Xcode" >&2
  echo "    2. Re-run with your 10-character team id:" >&2
  echo "       DEVELOPMENT_TEAM=ABCDE12345 pnpm run xcode:release" >&2
  echo "" >&2
  echo "  Team id: developer.apple.com/account → Membership details" >&2
  echo "  Xcode must be signed in: Xcode → Settings → Accounts (Apple ID)" >&2
  exit 1
fi

ALLOW_PROVISIONING="${ALLOW_PROVISIONING_UPDATES:-1}"
CODE_SIGN_STYLE="${CODE_SIGN_STYLE:-Automatic}"

XCODE_ARGS=(
  -workspace "$WS"
  -scheme "$SCHEME"
  -configuration Release
  -destination "generic/platform=iOS"
  -archivePath "$ARCHIVE_PATH"
  archive
  DEVELOPMENT_TEAM="$DEVELOPMENT_TEAM"
  CODE_SIGN_STYLE="$CODE_SIGN_STYLE"
)

if [[ "$ALLOW_PROVISIONING" == "1" ]]; then
  XCODE_ARGS+=(-allowProvisioningUpdates)
fi

echo "==> xcodebuild release archive (physical device, no EAS)"
echo "    workspace: $WS"
echo "    scheme:    $SCHEME"
echo "    team:      $DEVELOPMENT_TEAM"
echo "    signing:   $CODE_SIGN_STYLE (allowProvisioningUpdates=$ALLOW_PROVISIONING)"
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
