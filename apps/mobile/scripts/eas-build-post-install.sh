#!/usr/bin/env bash
# EAS Install-dependencies hook: patch native modules, materialize pnpm deps for
# Metro, and clear stale Metro cache (fixes export:embed resolution on cloud).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> eas-build-post-install (cwd=$ROOT)"

# Match mobile-install.sh hoisted copy layout (pnpm isolated .pnpm breaks export:embed).
if command -v pnpm >/dev/null 2>&1; then
  pnpm install \
    --config.node-linker=hoisted \
    --config.package-import-method=copy \
    --config.optimistic-repeat-install=false \
    || true
fi

node scripts/mobile-patch-native.js
node scripts/ensure-metro-local-deps.js
node scripts/verify-eas-metro-resolve.js

echo "==> clear Metro cache"
rm -rf "${TMPDIR:-/tmp}/metro-cache" node_modules/.cache/metro .expo/metro 2>/dev/null || true

echo "OK eas-build-post-install"
