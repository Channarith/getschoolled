#!/usr/bin/env bash
# Estimate what EAS will upload and optionally materialize the archive locally.
# Run from apps/mobile: bash scripts/verify-eas-archive-size.sh
# Add --inspect to run `eas build:inspect` (requires eas-cli + network).
set -euo pipefail

ROOT="$(git -C "$(cd "$(dirname "$0")/.." && pwd)" rev-parse --show-toplevel)"
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
EASIGNORE="$ROOT/.easignore"

echo "==> EAS archive check"
echo "    git root:  $ROOT"
echo "    mobile:    $MOBILE"
echo "    easignore: $EASIGNORE"

if [[ ! -f "$EASIGNORE" ]]; then
  echo "ERROR: missing $EASIGNORE (EAS uploads the whole monorepo without it)" >&2
  exit 1
fi

# Rough size: apps/mobile source tree without native/deps caches.
mobile_kb="$(du -sk "$MOBILE/src" "$MOBILE/assets" "$MOBILE/scripts" "$MOBILE/plugins" \
  "$MOBILE/package.json" "$MOBILE/app.json" "$MOBILE/app.config.js" \
  "$MOBILE/eas.json" "$MOBILE/metro.config.js" "$MOBILE/babel.config.js" \
  "$MOBILE/tsconfig.json" "$MOBILE/tsconfig.typecheck.json" \
  "$MOBILE/pnpm-lock.yaml" "$MOBILE/App.tsx" "$MOBILE/index.ts" 2>/dev/null \
  | awk '{s+=$1} END {print s+0}')"
echo "    apps/mobile source (excl. native/deps): ~${mobile_kb} KB"

bloated_kb="$(cd "$ROOT" && du -sk docs output .eas-npm-cache apps/mobile/.pnpm-home 2>/dev/null \
  | awk '{s+=$1} END {print s+0}')"
echo "    local bloat now excluded by .easignore: ~${bloated_kb} KB"

if [[ "${1:-}" == "--inspect" ]]; then
  echo "==> eas build:inspect (archive stage)"
  cd "$MOBILE"
  OUT="${TMPDIR:-/tmp}/eas-archive-inspect-$$"
  mkdir -p "$OUT"
  eas build:inspect --platform ios --stage archive --output "$OUT" --profile production
  du -sh "$OUT"
  echo "    inspect output: $OUT"
fi

echo "OK (target archive: low tens of MB, not 900MB+)"
