speech service — speech gateway (AOEP / Salareen)
=================================================

Purpose
  Narration and language services: text-to-speech routing/synthesis, machine
  translation, the supported-language catalog, and language-learning exercises.
  TTS uses a graceful engine chain (ElevenLabs -> edge-tts neural -> on-device)
  and can route clone voices to Chatterbox / XTTS / CosyVoice when configured.

Package / entrypoint
  speech_gw  ->  services/speech/src/speech_gw/main.py   (NOTE: package name is
  speech_gw, not "speech")
Port
  8002 (local dev; :8000 in Docker/k8s)

Key endpoints
  GET  /languages
  POST /tts            GET /tts/engine   GET /tts/voices
  POST /translate      POST /delivery/plan   (per-student MT/TTS routing)
  /learn/*             (language-learning exercises / pronunciation)
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  ./scripts/run_local_service.sh speech
  # or: cd services/speech && PYTHONPATH=src uvicorn speech_gw.main:app --port 8002

Test
  cd services/speech && PYTHONPATH=src python -m pytest    # or: make test

Notes
  - Heavy TTS/translation providers target real endpoints; offline they fall
    back (device voice / no-op translate) so callers never hard-fail.

See also: .cursor/skills/speech-tts, packages/shared/src/aoep_shared/languages.py,
docs/api-reference.txt.
