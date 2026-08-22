#!/usr/bin/env bash
# Pre-generate neural voice clips for all 28 supported languages, then start the server.
# Clips are keyed by (voice, rate, text) and stored in $MUSIC_LAB_TTS_CACHE.
# Already-cached clips are skipped, so re-deploys are fast (seconds, not minutes).
set -euo pipefail

    LANGS=(
  en es it fr de pt nl pl ru uk tr ar he hi bn ur fa
  ja ko vi th id sw el cs zh km
)

echo "==> Music Lab voice prefetch starting (cache: ${MUSIC_LAB_TTS_CACHE:-~/.cache/theodore-music-lab/tts})"

# Build the --lang flags dynamically
LANG_FLAGS=()
for lang in "${LANGS[@]}"; do
  LANG_FLAGS+=("--lang" "$lang")
done

# Run the prefetch; tolerate partial failures (Microsoft TTS throttles at high burst).
# Exit 0 = all good; exit 1 = some clips failed (server still starts).
python3 scripts/prefetch_voices.py "${LANG_FLAGS[@]}" || {
  echo "!! prefetch finished with some failures — already-cached clips still work; server starting anyway."
}

echo "==> Starting Theodore Music Lab on :8000"
exec uvicorn "theodore_music_lab.main:app" \
     --host 0.0.0.0 \
     --port 8000 \
     --workers 1 \
     --log-level info
