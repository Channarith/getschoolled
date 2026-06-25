# Shared Node/Metro heap + Expo defaults for all mobile bash scripts.
# Source from other scripts:  . "$(dirname "$0")/mobile-env.sh"

# Mac Node 22 defaults to ~4 GB — Metro/Expo OOM during crawl (AfterScanDir).
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=12288}"
export METRO_NODE_OPTIONS="${METRO_NODE_OPTIONS:-$NODE_OPTIONS}"
export EXPO_NO_TELEMETRY="${EXPO_NO_TELEMETRY:-1}"
