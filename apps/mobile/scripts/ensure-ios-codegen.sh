#!/usr/bin/env bash
# Pre-generate React Native codegen artifacts before xcodebuild.
#
# RN 0.74 + Xcode 15+/26: React-Codegen lists generated .cpp files as compile
# inputs but only creates them in a before_compile script phase. On a clean
# ios/build (release script wipes it; first local build after prebuild) Xcode
# validates inputs before the script runs and fails with:
#   Build input file cannot be found: .../rnsvg/ComponentDescriptors.cpp
#
# pod install also runs codegen, but mobile-ios-pod-refresh.sh often skips pod
# install when Pods are already OK — so we always ensure artifacts here.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  exit 0
fi

if [[ ! -d ios ]]; then
  echo "ensure-ios-codegen: ios/ missing — skip" >&2
  exit 0
fi

CODEGEN_JS="node_modules/react-native/scripts/generate-codegen-artifacts.js"
if [[ ! -f "$CODEGEN_JS" ]]; then
  echo "ERROR: $CODEGEN_JS missing — run pnpm install in apps/mobile" >&2
  exit 1
fi

MARKER="ios/build/generated/ios/react/renderer/components/rnsvg/ComponentDescriptors.cpp"
if [[ -f "$MARKER" && "${FORCE_IOS_CODEGEN:-0}" != "1" ]]; then
  echo "==> iOS codegen artifacts OK ($MARKER)"
  exit 0
fi

echo "==> Generating iOS codegen artifacts (react-native-svg / React-Codegen)"
node "$CODEGEN_JS" -p . -t ios -o ios

if [[ ! -f "$MARKER" ]]; then
  echo "ERROR: codegen finished but $MARKER is still missing" >&2
  exit 1
fi

echo "==> iOS codegen artifacts ready"
