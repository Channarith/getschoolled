#!/usr/bin/env bash
# Expo export with heap headroom — one platform per Node process (Mac OOM fix).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MOBILE_ROOT="$ROOT"
. "$(dirname "$0")/mobile-deps.sh"

VERBOSE="${VERBOSE:-0}"
PLATFORMS=()

usage() {
  echo "usage: $0 [ios] [android]" >&2
  echo "  (no args = ios then android, separate processes)" >&2
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    ios|android) PLATFORMS+=("$1"); shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

if [ "${#PLATFORMS[@]}" -eq 0 ]; then
  PLATFORMS=(ios android)
fi

if [ ! -f app.json ]; then
  echo "ERROR: run from apps/mobile (app.json missing)" >&2
  exit 1
fi

if ! mobile_deps_has_expo; then
  echo "ERROR: expo missing — bash scripts/mobile-install.sh" >&2
  exit 1
fi

# Metro subprocess may ignore NODE_OPTIONS; set both (expo-cli #2401).
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=8192}"
export METRO_NODE_OPTIONS="${METRO_NODE_OPTIONS:-$NODE_OPTIONS}"
export EXPO_NO_TELEMETRY=1
# Export is non-interactive — skip dev-oriented file watchers where possible.
export CI="${CI:-true}"

EXPO_BIN="node_modules/.bin/expo"
if [ ! -e "$EXPO_BIN" ]; then
  EXPO_BIN="node_modules/expo/bin/cli"
fi

echo "==> mobile export"
echo "    cwd=$PWD"
echo "    platforms=${PLATFORMS[*]}"
echo "    NODE_OPTIONS=$NODE_OPTIONS"
echo "    METRO_NODE_OPTIONS=$METRO_NODE_OPTIONS"

for platform in "${PLATFORMS[@]}"; do
  echo "    exporting $platform..."
  EXPO_ARGS=(export --output-dir dist --platform "$platform")
  if [ "$VERBOSE" = "1" ]; then
    EXPO_ARGS+=(--dump-sourcemap)
    export EXPO_DEBUG=1
  fi
  # Separate process per platform so heap is released between ios and android.
  if [ -x "$EXPO_BIN" ]; then
    "$EXPO_BIN" "${EXPO_ARGS[@]}"
  else
    node node_modules/expo/bin/cli "${EXPO_ARGS[@]}"
  fi
  echo "OK export:$platform"
done

echo "OK export -> dist/"
