#!/usr/bin/env bash
# Lightweight environment check — pure bash, no pnpm/Node heap required.
# Run directly:  bash scripts/mobile-doctor.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MOBILE_ROOT="$ROOT"
. "$(dirname "$0")/mobile-deps.sh"
VERBOSE="${VERBOSE:-0}"
FAILURES=0
WARNINGS=0

ok()   { echo "  OK   $*"; }
warn() { WARNINGS=$((WARNINGS + 1)); echo "  WARN $*"; }
fail() { FAILURES=$((FAILURES + 1)); echo "  FAIL $*"; }

echo "Salareen mobile — environment doctor (bash)"
echo
echo "Platform: $(uname -s) $(uname -m)"
echo "CWD:      $PWD"

if [ ! -f app.json ]; then
  fail "app.json not found — run from apps/mobile (monorepo: cd path/to/getschoolled/apps/mobile)"
fi

if command -v node >/dev/null 2>&1; then
  NODE_VER="$(node -v 2>/dev/null || true)"
  NODE_MAJOR="${NODE_VER#v}"
  NODE_MAJOR="${NODE_MAJOR%%.*}"
  if [ -n "${NODE_MAJOR}" ] && [ "${NODE_MAJOR}" -ge 18 ] 2>/dev/null; then
    ok "Node ${NODE_VER}"
  else
    fail "Node ${NODE_VER:-missing} — need Node 18+"
  fi
else
  fail "node not on PATH"
fi

if mobile_deps_has_expo; then
  ok "expo CLI present"
elif [ -d node_modules ]; then
  fail "node_modules exists but expo is missing — run: bash scripts/mobile-install.sh"
else
  fail "node_modules missing — run: bash scripts/mobile-install.sh"
fi

if [ -d node_modules/babel-preset-expo ]; then
  ok "babel-preset-expo installed"
elif [ -d node_modules ]; then
  warn "babel-preset-expo missing — run: bash scripts/mobile-install.sh"
else
  warn "babel-preset-expo missing — node_modules not installed"
fi

if mobile_deps_has_tsc; then
  ok "typescript/tsc present"
elif [ -d node_modules ]; then
  fail "node_modules exists but tsc is missing — run: bash scripts/mobile-install.sh"
fi

if [ -f tsconfig.json ]; then
  if grep -qE '"\*\*/\*\.(ts|tsx)"' tsconfig.json 2>/dev/null; then
    fail 'tsconfig.json include is too broad ("**/*.ts" → OOM). git fetch origin && git pull origin main'
  else
    INC="$(grep -A20 '"include"' tsconfig.json 2>/dev/null | head -8 | tr '\n' ' ')"
    ok "tsconfig.json include looks scoped (${INC:-ok})"
  fi
else
  fail "tsconfig.json missing"
fi

if [ -f scripts/mobile-typecheck.sh ]; then
  ok "mobile-typecheck.sh present"
else
  fail "scripts/mobile-typecheck.sh missing — git fetch origin && git pull origin main"
fi

if [ -f scripts/mobile-expo.sh ]; then
  ok "mobile-expo.sh present (expo without pnpm heap OOM)"
else
  fail "scripts/mobile-expo.sh missing — git pull origin main"
fi

if [ -f tsconfig.typecheck.json ]; then
  ok "tsconfig.typecheck.json present"
else
  fail "tsconfig.typecheck.json missing — git fetch origin && git pull origin main"
fi

if [ -f package.json ]; then
  if grep -q 'mobile-typecheck.sh' package.json 2>/dev/null; then
    ok "package.json typecheck uses preflight script"
  else
    fail 'package.json typecheck still runs raw tsc — git fetch origin && git pull origin main'
  fi
  if grep -q 'listFilesOnly' package.json 2>/dev/null; then
    fail "typecheck:verbose uses --listFilesOnly (OOM on Mac) — git pull origin main"
  elif grep -q 'mobile-typecheck.sh' package.json 2>/dev/null; then
    ok "package.json typecheck:verbose uses preflight script"
  fi
  if grep -q 'mobile-doctor.sh' package.json 2>/dev/null; then
    ok "package.json doctor uses bash script"
  fi
else
  fail "package.json missing"
fi

NM_DIRS="$(find node_modules -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
if [ "${NM_DIRS}" -gt 2000 ] 2>/dev/null; then
  warn "node_modules has ${NM_DIRS} top-level entries — pnpm run may OOM on Mac; use bash scripts directly"
fi

if [ "$(uname -s)" = "Darwin" ]; then
  echo
  echo "macOS / iOS Simulator checks:"
  if xcode-select -p >/dev/null 2>&1; then
    ok "Xcode CLI: $(xcode-select -p)"
  else
    fail "Xcode Command Line Tools not found"
  fi
  SIMS="$(xcrun simctl list devices available 2>/dev/null | grep -E 'iPhone|iPad' | head -3 || true)"
  if [ -n "$SIMS" ]; then
    ok "Simulators available"
    echo "$SIMS" | sed 's/^/       /'
  else
    warn "No iOS simulators listed — Xcode -> Settings -> Platforms"
  fi
fi

echo
echo "Android emulator checks (optional):"
ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
if [ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME" ]; then
  ok "ANDROID_HOME=$ANDROID_HOME"
else
  warn "ANDROID_HOME unset — needed only for Android emulator"
fi

echo
echo "If pnpm/expo OOMs on Mac (AfterScanDir, ~4 GB heap):"
echo "  All scripts set NODE_OPTIONS + METRO_NODE_OPTIONS=12GB."
echo "  Prefer bash launchers (never raw 'expo' or 'pnpm exec expo'):"
echo "    bash scripts/mobile-launch-ios.sh"
echo "    bash scripts/mobile-launch-android.sh"
echo "    bash scripts/mobile-expo.sh start --ios --clear"
echo "If deps are missing after pnpm install:"
echo "  bash scripts/mobile-install.sh"
echo "If pnpm run doctor OOMs, skip pnpm and run:"
echo "  bash scripts/mobile-doctor.sh"
echo "  bash scripts/mobile-typecheck.sh"
echo "  VERBOSE=1 bash scripts/mobile-typecheck.sh"

if [ "$VERBOSE" = "1" ]; then
  echo
  echo "Verbose diagnostics:"
  command -v pnpm >/dev/null && ok "pnpm $(pnpm --version 2>/dev/null || echo present)" || warn "pnpm not on PATH"
  [ -f VERSION ] && ok "repo VERSION $(head -1 VERSION 2>/dev/null)" || true
  echo "  node_modules top-level dirs: ${NM_DIRS:-unknown}"
  mobile_deps_print_status
  echo "  git HEAD: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi

echo
if [ "$FAILURES" -gt 0 ]; then
  echo "Result: ${FAILURES} failure(s), ${WARNINGS} warning(s) — fix FAIL items first."
  exit 1
fi
echo "Result: ready (${WARNINGS} warning(s)). Try: pnpm run dev:ios"
exit 0
