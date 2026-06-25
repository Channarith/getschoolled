# Shared Node/Metro heap + Expo defaults for all mobile bash scripts.
# Source from other scripts:  . "$(dirname "$0")/mobile-env.sh"

# Mac Node 22 defaults to ~4 GB — Metro/Expo OOM during crawl (AfterScanDir).
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=12288}"
export METRO_NODE_OPTIONS="${METRO_NODE_OPTIONS:-$NODE_OPTIONS}"
export EXPO_NO_TELEMETRY="${EXPO_NO_TELEMETRY:-1}"
# Non-interactive: no "Use port 8082?" prompts (Metro port is fixed in launch scripts).
export CI="${CI:-1}"
# EXPO_OFFLINE is NOT set here — launch scripts enable it only when Expo Go is
# already on the simulator/emulator. Offline on first launch blocks Expo Go install.
