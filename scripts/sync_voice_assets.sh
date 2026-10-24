#!/usr/bin/env bash
# Publish pre-rendered demo narration to Vultr Object Storage (never git). Thin wrapper over tts_bakeoff.demo_voice.assets:
#   scripts/sync_voice_assets.sh [sync|withdraw|cors|policy|status] [args]     (default: sync)
#   scripts/sync_voice_assets.sh sync --dry-run          # prints the aws commands; no credentials, no network
# Credentials: VOICE_ASSETS_ACCESS_KEY/SECRET_KEY, AWS_ACCESS_KEY_ID/SECRET, AWS_PROFILE or OBJECT_STORE_ACCESS_KEY/SECRET
# (environment or config/local.env). See docs/demo-voice.txt.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "${1:-}" in sync|withdraw|cors|policy|status) cmd="$1"; shift ;; *) cmd=sync ;; esac
exec env PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m tts_bakeoff.demo_voice.assets "$cmd" "$@"
