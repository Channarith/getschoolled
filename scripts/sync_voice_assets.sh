#!/usr/bin/env bash
# Ship pre-rendered demo narration to object storage (not git). Run after render_demo_voice.sh + `render publish`.
#   VOICE_ASSETS_BUCKET=salareen-prod AWS_ENDPOINT_URL=https://sjc1.vultrobjects.com scripts/sync_voice_assets.sh [ASSETS_DIR]
# Credentials come from the usual AWS_* env vars, never from this repo. Clips land under s3://<bucket>/voice-assets/.
# The bucket needs public read for that prefix (or CDN) and, if the site is on another origin, CORS for GET/HEAD.
set -euo pipefail
SRC="${1:-${GS_VOICE_ASSETS:-$HOME/voice-assets}}"
: "${VOICE_ASSETS_BUCKET:?set VOICE_ASSETS_BUCKET}"
[[ -f "$SRC/voices.json" ]] || { echo "no $SRC/voices.json: run 'python3 -m tts_bakeoff.demo_voice.render publish' first" >&2; exit 65; }
# --delete removes clips of a voice whose consent was withdrawn (prune-revoked deletes them locally first).
aws s3 sync "$SRC" "s3://$VOICE_ASSETS_BUCKET/voice-assets/" --delete --exclude "*.json" --cache-control "public, max-age=31536000, immutable"
aws s3 sync "$SRC" "s3://$VOICE_ASSETS_BUCKET/voice-assets/" --exclude "*" --include "voices.json" --include "*/index.json" \
  --cache-control "no-cache"
echo "published. Site base URL: set NEXT_PUBLIC_VOICE_ASSETS_URL (web) to the bucket URL, or copy $SRC to apps/web/public/voice-assets."
