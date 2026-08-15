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
   MediaRecorder makes complete low-latency WebM/MP4 windows: 1.2 seconds for a
   known language (0.8-second Fast option), 2.0 seconds for Auto because language
   ID needs more speech. It uploads to an OpenAI-compatible
   /v1/audio/transcriptions endpoint. Raw audio is never persisted by the lab.

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

Realtime Theodore replies and teaching
--------------------------------------
Theodore can participate in the same live session rather than only reading the
translation feed:

- Enable "Theodore replies after each learner turn".
- Reply language can follow the detected learner language (`same`) or be any of
  the 27 platform languages.
- Modes: Teach + check, Answer directly, Coach with a hint, Clarify simply.
- Browser Speech final results are natural end-of-turn signals, so Theodore can
  reply immediately. Server Whisper windows are buffered and Theodore waits for
  an adaptive-gate silence window before replying, avoiding an interruption
  every 0.8–2.0 seconds.
- Real open-ended teaching uses XAI_API_KEY. The system prompt requires the
  selected language, under three short spoken sentences, and one teaching action.
- Without xAI, Theodore uses a safe English teaching template and asks NLLB/xAI
  translation for the reply language. If translation is unavailable, it remains
  English AND the reply language/voice stays English with a visible warning.
- Theodore replies are broadcast over WebSocket to speaker, teacher, customer,
  and viewer clients.
- Explicit API: POST /api/sessions/{id}/theodore/reply. Status:
  GET /api/theodore/status.


Theodore's voice (server neural audio, device voice as fallback)
---------------------------------------------------------------
"Speak Theodore aloud" is on by default, and so is auto-reply, so a learner turn
produces spoken teaching without touching a checkbox. Audio is rendered by the
first engine that is actually configured:

  speech gateway /tts  ->  ElevenLabs  ->  edge-tts neural  ->  device voice

The browser's own speechSynthesis is LAST on purpose. It has no usable voice for
most of the 27 languages, so a Khmer or Tamil reply used to be silent or robotic
while the badge still claimed it had spoken. The page probes GET /api/tts/status
once; when no engine exists the server answers 501 (not 500) and the page falls
back to the device voice rather than going quiet. The badge always names what
spoke — "speaking Khmer · elevenlabs" or "· device voice".

Pick an engine:
  TTS_BASE_URL / SPEECH_BASE_URL   AOEP speech gateway (POST /tts -> audio bytes)
  ELEVENLABS_API_KEY               best quality; eleven_multilingual_v2
  pip install -e 'subrepos/theodore_audio_translation_lab[speech]'
                                   edge-tts neural voices, no key required

Endpoints:
  GET  /api/tts/status                        {available, engine, engines, note}
  GET  /api/tts?text=...&language=km          audio bytes (GET so <audio src> works)
  POST /api/tts                               same, for larger bodies
Responses carry X-TTS-Engine so you can see which engine served the audio.
"Say it again" replays the last reply; "Stop Theodore audio" cancels both server
audio and any device utterance.


Troubleshooting xAI ("Translation unavailable" / HTTP 400)
---------------------------------------------------------
A valid XAI_API_KEY that still fails with

  ⚠ Translation unavailable ... Provider errors: xai: HTTP Error 400: Bad Request

was almost always a retired model. xAI removed the grok-2 family from the API in
January 2026, and this lab used to default to XAI_MODEL=grok-2-1212, so a correct
key got a blanket 400. The default is now grok-4.3 (a current canonical model;
grok-4.5 exists but is not offered to EU API Console accounts, so it is not a
safe default). Override with XAI_MODEL.

The old message was also unhelpful because urllib's HTTPError stringifies as just
"HTTP Error 400: Bad Request" and throws away the response body — which is the
only place xAI explains itself. Errors now carry that body, name the model that
failed, and suggest the current default:

  xai: xAI HTTP 400 for model 'grok-2-1212': {"error":"The model does not
  exist"} The configured model is 'grok-2-1212'; set XAI_MODEL to a current one
  (default is grok-4.3).

Check what the server is actually using:
  curl -s http://127.0.0.1:8099/api/theodore/status | python3 -m json.tool
  # -> "xai_model": "grok-4.3", plus a "speech" block for the voice chain

Audio policy and quality telemetry
----------------------------------
audio_policy.AudioPolicy is one frozen dataclass of 30+ knobs (capture windows,
the Web Audio filter/compressor chain, the adaptive noise gate, provider
timeouts, Theodore reply shaping, and latency/quality targets). Read it at
GET /api/audio-policy and live-tune it with PATCH /api/audio-policy (partial
knob dict; {"reset": true} reloads env defaults). quality_telemetry records
per-session counters/gauges (transcripts, ASR/MT latency, phrasebook vs
source-fallback coverage, gate skips, viewer peaks, a computed quality score)
at GET /api/sessions/{id}/telemetry and GET /api/telemetry/overview.
Server-Whisper chunks are treated as end-of-turn so silence-ended windows
trigger Theodore's auto-reply. The offline phrasebook covers 40+ common
classroom phrases across en/es/fr/zh/km.

This supports all 27 language codes at the routing/provider level; natural
quality requires a live xAI model or NLLB translation provider for that language.
The lab never claims an English fallback is a 27-language response.

Languages
---------
English, Spanish, French, German, Italian, Portuguese, Dutch, Polish, Russian,
Ukrainian, Turkish, Arabic, Hebrew, Hindi, Bengali, Urdu, Persian, Mandarin
Chinese, Japanese, Korean, Vietnamese, Thai, Indonesian, Swahili, Greek, Czech,
and Khmer (27 total).

Screens
-------
docs/screens/theodore_audio_translation_lab.webp
  (also under this subrepo at docs/screens/theodore_audio_translation_lab.webp)
  Capture panel (mic/webcam, gate, ASR) and live multilingual translation feed
  with Theodore replies.

Regenerate after UI changes:
  python3 scripts/render_lab_docs_screenshots.py

STEP BY STEP (from repo root)
-----------------------------
Works offline with the phrasebook fallback. Mic optional — use the debug text
box if the browser has no microphone permission.

Step 0 — activate the project venv

  cd "$(git rev-parse --show-toplevel)"
  . .venv/bin/activate
  python3 -m pip install -e 'subrepos/theodore_audio_translation_lab[all]'

Step 1 — run the automated tests

  PYTHONPATH=subrepos/theodore_audio_translation_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_audio_translation_lab/tests -q

Step 2 — start the lab UI

  PYTHONPATH=subrepos/theodore_audio_translation_lab/src \
    python3 subrepos/theodore_audio_translation_lab/scripts/run_lab.py
  # default port 8041; or:
  #   python3 -m uvicorn theodore_audio_translation_lab.main:app \
  #     --app-dir subrepos/theodore_audio_translation_lab/src --port 8041

  Check:  curl -s http://127.0.0.1:8041/health
  # status=ok, languages=27
  Open:   http://127.0.0.1:8041/lab

Step 3 — start a speaker session

  1. Allow mic (or use the manual / debug text input)
  2. Pick source language (or Auto — requires Whisper / ASR_BASE_URL)
  3. Click Start session
  4. Speak a short classroom phrase (e.g. "Buenos días clase")
     or type it into the debug box and submit

  Expect interim then final transcript cards on the right. Compare against
  docs/screens/theodore_audio_translation_lab.webp.

Step 4 — join as Theodore / teacher / viewer

  Open the shareable viewer link (or a second tab) with a different target
  language + role. Final transcripts fan out translated; interim stays source
  text by default.

  Enable "Theodore replies after each learner turn" to get a short spoken
  teach/coach/clarify reply (xAI when XAI_API_KEY is set; otherwise English
  template + translation when available).

Step 5 — tune quality + check telemetry

  curl -s http://127.0.0.1:8041/api/audio-policy | python3 -m json.tool
  curl -s http://127.0.0.1:8041/api/telemetry/overview | python3 -m json.tool

  Headphones recommended so Speak-translated-audio does not loop into the mic.
  Provider wiring (Whisper / NLLB / xAI) is under Provider setup below.

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
  XAI_MODEL=grok-4.3
  TTS_BASE_URL=http://127.0.0.1:8002     (server neural voice for Theodore)
  ELEVENLABS_API_KEY=...                 (best-quality Theodore voice)
  ELEVENLABS_MODEL=eleven_multilingual_v2
  AOEP_TTS_VOICE_KM=km-KH-SreymomNeural  (per-language edge-tts override)
  TTS_TIMEOUT_S=20
  AUDIO_CAPTURE_WINDOW_MS=1200
  AUDIO_AUTO_WINDOW_MS=2000
  AUDIO_HIGHPASS_HZ=80
  AUDIO_LOWPASS_HZ=7500
  AUDIO_GATE_MARGIN_DB=9
  AUDIO_ABSOLUTE_GATE_DB=-48
  AUDIO_MIN_SPEECH_RATIO=0.12

How to use
----------
Speaker / learner:
1. Enter a shared session ID.
2. Choose spoken language and desired local translation.
3. Leave role = Speaker / learner.
4. Click Start webcam + translation and allow camera/microphone.
5. Change Spoken language at ANY time. Browser recognition is stopped and
   restarted with the new BCP-47 language without dropping the session/viewers.

Automatic input-language detection:
- Choose "Auto-detect (server Whisper)" under Spoken language.
- Auto-detect requires ASR_BASE_URL. The lab omits Whisper's language hint,
  requests verbose_json, then uses the detected language returned for EACH
  2.0-second audio window. This supports a speaker changing languages mid-call.
- Browser Web Speech recognition cannot reliably auto-detect: its API requires
  a language hint. The UI refuses Auto when server Whisper is unavailable rather
  than pretending it can detect.
- The detected language appears in the status bar and on every translation card.
- You can switch from Auto to a specific language (or between any two languages)
  while recording; connected Theodore/teacher/customer viewers receive a live
  config update and remain connected.

Bluetooth, USB, and other microphones
------------------------------------
- Click Allow / refresh microphones after opening the lab. Browsers hide device
  names until microphone permission is granted.
- The input picker lists every `audioinput` returned by `enumerateDevices()`:
  Bluetooth headsets, USB microphones/audio interfaces, wired headsets, and
  built-in microphones. Hot-plug changes refresh automatically.
- Selecting a different mic while running rebuilds the filtered capture stream
  and restarts capture WITHOUT closing the session or viewer WebSockets.
- Explicit device selection uses `deviceId: {exact: ...}` and server Whisper.
  This is necessary because the browser Web Speech API cannot consume a chosen
  MediaStream; it always uses the OS/browser default input. Without ASR_BASE_URL,
  make the Bluetooth/USB mic the OS default and use Browser realtime ASR.
- The UI shows the active track label, actual sample rate and channel count.
- On iOS/Android browsers, available Bluetooth routing is ultimately controlled
  by the OS and browser. A native app can offer stronger routing controls.

Low delay + noise filtering
---------------------------
- Browser recognition streams interim words immediately (lowest delay).
- Server defaults to complete 1.2-second windows; choose Fast for 0.8 seconds.
  Auto-detect enforces at least 2.0 seconds for reliable language identification.
- Microphone constraints request echoCancellation, noiseSuppression,
  autoGainControl, mono, 16 kHz, and low interactive latency.
- Server-bound audio passes through a real Web Audio chain: 80 Hz high-pass
  (rumble/hum), 7.5 kHz low-pass (unneeded high-frequency noise), and dynamics
  compressor (more consistent speech level).
- The first 900 ms calibrates the room noise floor. An adaptive gate uses the
  floor + 9 dB (never below -48 dB) and requires 12% speech-active frames.
  Silence/noise windows are skipped before upload, saving ASR cost and delay.
- The UI shows room noise, gate threshold, voice ratio, capture/ASR/translation/
  total latency, and whether silence was skipped. All thresholds/windows can be
  tuned with AUDIO_* env vars or the latency selector.

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
