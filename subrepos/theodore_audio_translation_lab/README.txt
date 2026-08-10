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
