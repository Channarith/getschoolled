#!/usr/bin/env bash
# Listen → LLM reply → speak (language of choice) — local stack on Spark.
#
#   ./scripts/run_voice_conversation.sh
#   → open http://127.0.0.1:8040/studio
#   Pick a course language, use Talk / mic, Theodore answers and CosyVoice speaks.
#
# Stack:
#   CosyVoice :9880  → speech gateway /tts
#   Speech    :8002  → NLLB /translate + CosyVoice TTS
#   Studio    :8040  → mic/ASR → voice/respond → /api/studio/tts
#
# Optional open LLM (else course-grounded local-fallback + NLLB):
#   export LLM_BASE_URL=http://127.0.0.1:8000/v1
#   export LLM_MODEL=education-base
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
source .venv/bin/activate

export SPEECH_BASE_URL="${SPEECH_BASE_URL:-http://127.0.0.1:8002}"
export TRANSLATION_BASE_URL="${TRANSLATION_BASE_URL:-$SPEECH_BASE_URL}"
export COSYVOICE_URL="${COSYVOICE_URL:-http://127.0.0.1:9880}"
export RATE_LIMIT_DISABLED="${RATE_LIMIT_DISABLED:-1}"
export VOICE_NLLB_LOCALIZE="${VOICE_NLLB_LOCALIZE:-1}"

echo "== CosyVoice =="
if ! curl -sf "$COSYVOICE_URL/health" >/dev/null; then
  echo "starting CosyVoice…"
  ./scripts/run_cosyvoice_local.sh || true
  sleep 2
fi
curl -s "$COSYVOICE_URL/health" | head -c 200; echo

echo "== Speech gateway (NLLB + CosyVoice TTS) =="
if ! curl -sf "$SPEECH_BASE_URL/health" >/dev/null; then
  echo "starting speech on :8002…"
  nohup env RATE_LIMIT_DISABLED="$RATE_LIMIT_DISABLED" COSYVOICE_URL="$COSYVOICE_URL" \
    PYTHONPATH=services/speech/src:packages/shared/src \
    python3 -m uvicorn speech_gw.main:app --host 0.0.0.0 --port 8002 \
    > output/speech_voice_loop.log 2>&1 &
  sleep 3
fi
echo -n "tts: "; curl -s "$SPEECH_BASE_URL/tts/status"; echo
echo -n "nllb: "; curl -s -X POST "$SPEECH_BASE_URL/translate" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello","source":"en","target":"es"}'; echo

echo "== Course Studio =="
if ! curl -sf http://127.0.0.1:8040/health >/dev/null; then
  echo "start Course Studio separately if needed (uvicorn on :8040)"
else
  curl -s http://127.0.0.1:8040/api/studio/voice/status | python3 -m json.tool | head -40
fi

cat <<EOF

Open:  http://127.0.0.1:8040/studio
Flow:  mic/Talk → /api/studio/teach/voice/respond (LLM or local-fallback)
                 → NLLB localize to course language
                 → /api/studio/tts (CosyVoice)

Unset XAI_API_KEY to force the free path. Set LLM_BASE_URL for a real local LLM.
EOF
