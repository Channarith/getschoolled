# Shared Node/Metro heap + Expo defaults for all mobile bash scripts.
# Source from other scripts:  . "$(dirname "$0")/mobile-env.sh"

# Mac Node 22 defaults to ~4 GB — Metro/Expo OOM during crawl (AfterScanDir).
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=12288}"
export METRO_NODE_OPTIONS="${METRO_NODE_OPTIONS:-$NODE_OPTIONS}"
export EXPO_NO_TELEMETRY="${EXPO_NO_TELEMETRY:-1}"
# Do NOT set CI=1 here. Launch scripts pass --port 8081 (no port prompt) and set
# CI=false so Metro watch mode works and Expo Go can open the project.
# EXPO_OFFLINE is set by launch scripts after Expo Go is installed (uses local
# expo/bundledNativeModules.json — avoids hang on expo.dev fetch).

export MOBILE_DEPLOY_MODE="${MOBILE_DEPLOY_MODE:-cloud}"
export MOBILE_CLOUD_BASE_URL="${MOBILE_CLOUD_BASE_URL:-https://www.salareen.com}"

# Gradle/Expo autolinking Node subprocesses must resolve from apps/mobile/node_modules,
# not ~/node_modules/.pnpm (symlinks outside the project break native Android builds).
_MOBILE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NODE_PATH="${_MOBILE_ROOT}/node_modules${NODE_PATH:+:${NODE_PATH}}"
