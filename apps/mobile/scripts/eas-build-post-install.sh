#!/usr/bin/env bash
# EAS Install-dependencies hook: patch native modules, materialize pnpm deps for
# Metro, and clear stale Metro cache (fixes export:embed resolution on cloud).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> eas-build-post-install (cwd=$ROOT)"

node scripts/mobile-patch-native.js
node scripts/ensure-metro-local-deps.js

echo "==> clear Metro cache"
rm -rf "${TMPDIR:-/tmp}/metro-cache" node_modules/.cache/metro .expo/metro 2>/dev/null || true

echo "OK eas-build-post-install"
