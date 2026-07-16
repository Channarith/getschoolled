#!/usr/bin/env bash
# Standalone RELEASE Android APK: JS bundle embedded (no Metro / no localhost),
# backend pinned to the cloud/Vultr host. Installable on any device.
#
# Usage (from apps/mobile):
#   bash scripts/mobile-build-release-android.sh
#   MOBILE_CLOUD_BASE_URL=https://www.salareen.com bash scripts/mobile-build-release-android.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MOBILE_ROOT="$ROOT"
# shellcheck source=mobile-env.sh
. "$(dirname "$0")/mobile-env.sh"
# shellcheck source=mobile-deps.sh
. "$(dirname "$0")/mobile-deps.sh"

# Make sure the full native dependency tree is materialized BEFORE prebuild, so
# the generated android/ can resolve react-native's Gradle version catalog
# (a no-op `pnpm install` otherwise leaves node_modules incomplete and gradle
# fails with "libs.versions.toml doesn't exist").
mobile_deps_ensure_installed

# Force cloud backend so the embedded bundle never points at localhost.
export MOBILE_DEPLOY_MODE=cloud
export MOBILE_CLOUD_BASE_URL="${MOBILE_CLOUD_BASE_URL:-https://www.salareen.com}"

echo "==> Standalone release APK"
echo "    backend: $MOBILE_CLOUD_BASE_URL (cloud)"

# Version stamp for the artifact filename (kept in sync by scripts/bump_pr_version.py).
VERSION_NAME="$(python3 -c "import json;print(json.load(open('app.json'))['expo'].get('version','0.0.0'))")"
VERSION_CODE="$(python3 -c "import json;print(json.load(open('app.json'))['expo'].get('android',{}).get('versionCode',0))")"
echo "    version: $VERSION_NAME (versionCode $VERSION_CODE)"

# Fresh build (no cached artifacts): --clean prebuild + gradle clean before
# assembleRelease so the APK is rebuilt from scratch and always carries the
# current version, not a stale incremental output.
npm run native:prebuild:android

(
  cd android
  ./gradlew clean assembleRelease
)

APK="$ROOT/android/app/build/outputs/apk/release/app-release.apk"
if [[ ! -f "$APK" ]]; then
  echo "ERROR: release APK not found under android/app/build/outputs/apk/release/" >&2
  exit 1
fi

# Guardrail: a standalone APK MUST embed the JS bundle, or it crashes on a device
# with "Unable to load script". Fail loudly here instead of shipping it.
bash "$(dirname "$0")/mobile-verify-apk-bundle.sh" "$APK"

# Publish to a consistent releases folder with a version-stamped filename so
# every build is traceable and never overwrites a different version.
OUT_DIR="$ROOT/dist/android"
mkdir -p "$OUT_DIR"
OUT_APK="$OUT_DIR/salareen-${VERSION_NAME}-${VERSION_CODE}-release.apk"
cp -f "$APK" "$OUT_APK"

echo ""
echo "OK release APK (standalone, JS bundle embedded — no Metro needed):"
echo "  $OUT_APK"
echo "  (gradle output: $APK)"
echo "Install on a connected device: adb install -r \"$OUT_APK\""
