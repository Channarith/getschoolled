#!/usr/bin/env bash
# B-SEC-1 (QA V&V plan, Mobile dimension) — fail if QA/admin credentials leak
# into the exported JS bundle. A shipped release must carry no live credentials
# (risk R5): anyone unzipping the AAB/IPA can read module-level string constants.
#
# Usage:
#   scripts/mobile-bundle-scan.sh [scan-dir]
#
# With no argument, runs a PRODUCTION-profile expo export into a temp dir and
# scans it (this is what CI does). With a dir argument, scans that directory —
# used to point the scan at a pre-built bundle, or to self-test the gate.
#
# The fix that makes this pass: QA quick-fill accounts live in app.config.js
# `extra.qaTestAccounts`, populated for every profile EXCEPT production (see
# app.config.js + src/config.ts). A production export resolves them to [] so no
# credentials reach the bundle.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SCAN_DIR="${1:-}"
CLEANUP_ROOT=""
if [ -z "$SCAN_DIR" ]; then
  CLEANUP_ROOT="$(mktemp -d)"
  SCAN_DIR="$CLEANUP_ROOT/dist"
  echo "==> exporting production-profile bundle for scan (this can take a minute)..."
  EAS_BUILD_PROFILE=production npx expo export --platform ios --output-dir "$SCAN_DIR" >/dev/null
fi

if [ ! -d "$SCAN_DIR" ]; then
  echo "FAIL: scan dir '$SCAN_DIR' does not exist" >&2
  exit 2
fi

# Live credentials that must never appear in a shipped bundle.
PATTERNS=('QaTest123' '88888888' 'admin@salareen.com' 'qa-pro@salareen.com')
# -I skips binary files: credentials that matter live in the text JS bundle
# (dist/_expo/static/js/*.js), not in media assets. Without it, generic patterns
# like "88888888" false-positive on byte sequences inside webp/mp3/png assets.
FOUND=0
for pat in "${PATTERNS[@]}"; do
  if grep -rIqF "$pat" "$SCAN_DIR" 2>/dev/null; then
    echo "FAIL: credential '$pat' found in exported bundle:" >&2
    grep -rIlF "$pat" "$SCAN_DIR" 2>/dev/null | sed 's/^/    /' >&2
    FOUND=1
  fi
done

[ -n "$CLEANUP_ROOT" ] && rm -rf "$CLEANUP_ROOT"

if [ "$FOUND" = 1 ]; then
  echo "" >&2
  echo "Bundle secret scan FAILED (B-SEC-1 / risk R5)." >&2
  echo "Move credentials into app.config.js \`extra.qaTestAccounts\` (non-production only)." >&2
  exit 1
fi

echo "OK: no leaked credentials in bundle (B-SEC-1)."
