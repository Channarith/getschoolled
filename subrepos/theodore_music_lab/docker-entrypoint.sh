#!/usr/bin/env bash
# Pre-generate neural voice clips for all 28 supported languages, then start the server.
# Clips are keyed by (voice, rate, text) and stored in $MUSIC_LAB_TTS_CACHE.
# Already-cached clips are skipped, so re-deploys are fast (seconds, not minutes).
set -euo pipefail

    LANGS=(
  en es it fr de pt nl pl ru uk tr ar he hi bn ur fa
  ja ko vi th id sw el cs zh km
)

# A full 28-language warmup can exhaust the 1Gi pod before /health answers.
# Clips are still generated on demand. Set MUSIC_LAB_PREFETCH=1 to warm the cache.
if [ "${MUSIC_LAB_PREFETCH:-0}" = "1" ]; then
  echo "==> Music Lab voice prefetch starting (cache: ${MUSIC_LAB_TTS_CACHE:-~/.cache/theodore-music-lab/tts})"
  LANG_FLAGS=()
  for lang in "${LANGS[@]}"; do
    LANG_FLAGS+=("--lang" "$lang")
  done
  (
    python3 scripts/prefetch_voices.py "${LANG_FLAGS[@]}" || echo "!! prefetch finished with some failures — already-cached clips still work."
  ) &
  disown || true
fi

echo "==> Starting Theodore Music Lab on :8000"
exec uvicorn "theodore_music_lab.main:app" \
     --host 0.0.0.0 \
     --port 8000 \
     --workers 1 \
     --log-level info
