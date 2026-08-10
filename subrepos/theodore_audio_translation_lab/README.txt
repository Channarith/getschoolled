Theodore Audio Translation Lab
==============================

Purpose
-------
A standalone experiment lab (like the webcam lab) for realtime webcam/
microphone speech translation across all 27 AOEP platform languages. A learner
speaks; Theodore, a teacher, customer, or viewer sees the source transcript and
their chosen translation immediately over a WebSocket feed.

What is real
------------
1. Browser/device realtime ASR
   The Web Speech API listens to the microphone and sends interim/final
   transcripts. This is the lowest-latency route; browser/OS support varies by
   language and may use the browser vendor's speech service.

2. Server Whisper ASR
   MediaRecorder makes complete 3.5-second WebM/MP4 windows and uploads them to
   an OpenAI-compatible /v1/audio/transcriptions endpoint. Configure ASR_BASE_URL.
   Raw audio is held in memory for the request and is NOT persisted by the lab.

3. Realtime translation fan-out
   Each viewer connects with a target language and role (Theodore, teacher,
   customer, viewer). Final transcripts are translated once per target language
   and delivered over WebSockets. Interim text is displayed without costly,
   flickery translation by default.

4. Provider chain
   AOEP speech gateway /translate (NLLB) -> xAI text translation -> tiny offline
   phrasebook -> honest source-text fallback. The lab never labels untranslated
   source text as translated and never invents an ASR transcript.

5. Translated audio
   Teachers/Theodore/customers can enable Speak translated audio. The browser/
   device TTS voice speaks each final translation in the target BCP-47 locale.
   Use headphones to keep that output from feeding back into the learner mic.

Important: xAI translates transcript TEXT; it does not transcribe microphone
AUDIO in this lab. Whisper/browser recognition performs ASR.

Languages
---------
English, Spanish, French, German, Italian, Portuguese, Dutch, Polish, Russian,
Ukrainian, Turkish, Arabic, Hebrew, Hindi, Bengali, Urdu, Persian, Mandarin
Chinese, Japanese, Korean, Vietnamese, Thai, Indonesian, Swahili, Greek, Czech,
and Khmer (27 total).

Standalone setup and launch
---------------------------
From inside the downloaded theodore_audio_translation_lab folder:

  python3 -m venv .venv
  . .venv/bin/activate                    # Windows: .venv\Scripts\activate
  python3 -m pip install -e '.[all]'
  python3 scripts/run_lab.py

Open: http://127.0.0.1:8041/lab

Quick smoke:

  curl -s http://127.0.0.1:8041/health
  # should report status=ok, languages=27 and provider readiness

Provider setup
--------------
Option A — browser recognition + xAI translation:

  export XAI_API_KEY=xai-...
  python3 scripts/run_lab.py

Option B — real server Whisper + AOEP NLLB translation:

  export ASR_BASE_URL=http://127.0.0.1:9000
  export ASR_MODEL=whisper-large-v3
  export ASR_API_KEY=...                    # optional for local endpoint
  export TRANSLATION_BASE_URL=http://127.0.0.1:8002
  python3 scripts/run_lab.py

ASR_BASE_URL must be OpenAI-compatible:

  POST $ASR_BASE_URL/v1/audio/transcriptions
  multipart: file, model, language, response_format=json
  response: {"text":"...", "language":"es", "confidence":0.9}

TRANSLATION_BASE_URL must expose the AOEP speech contract:

  POST $TRANSLATION_BASE_URL/translate
  {"text":"...", "source":"es", "target":"en"}
  -> {"source":"es", "target":"en", "text":"..."}

Other env:

  ASR_PATH=/v1/audio/transcriptions
  ASR_TIMEOUT_S=45
  ASR_MAX_AUDIO_BYTES=8388608
  TRANSLATION_TIMEOUT_S=15
  XAI_BASE_URL=https://api.x.ai/v1
  XAI_MODEL=grok-2-1212

How to use
----------
Speaker / learner:
1. Enter a shared session ID.
2. Choose spoken language and desired local translation.
3. Leave role = Speaker / learner.
4. Click Start webcam + translation and allow camera/microphone.
5. Auto mode uses browser recognition when available; choose Server Whisper
   chunks to test the configured server ASR path.

Teacher / Theodore / customer:
1. The speaker clicks Copy viewer link and chooses a role.
2. Open that link in a second browser/device.
3. Choose the target language before connecting if needed.
4. Final translations appear live; source text, provider, confidence/latency,
   and fallback warnings remain visible.

Debug without a microphone:
Type a sentence in the manual transcript box. It exercises translation +
WebSocket delivery without pretending to test ASR.

Privacy / production caveats
----------------------------
- This lab does not persist audio. Session transcript/translation history is
  in-memory only and disappears when the process restarts.
- Browser speech recognition may leave the device depending on browser/vendor.
- Before real customer use: add authentication/authorization, consent, retention
  policy, encrypted transport (HTTPS/WSS), rate limits, abuse controls, and an
  approved ASR/translation data-processing agreement.
- Headphones/echo cancellation are important in webcam classes so Theodore or
  another participant's audio is not re-transcribed as the learner.
- This lab is an integration harness, not yet wired into production live rooms.

Tests
-----
  PYTHONPATH=src python3 -m pytest tests -q
