PRIVATE Drive Mode fine-tune lab (Theodore / Salareen)
======================================================

Purpose
  Fine-tune Drive Mode hands-free audio agent quality before promoting knobs
  into apps/web /drive, mobile DriveModeScreen, and the speech gateway.

What it tunes
  - Wake-word precision/recall (Hey Sala / Salareen)
  - Echo rejection (narration bleed into mic)
  - Pause-to-submit delay, resume delay
  - TTS prosody hints / engine preference
  - Segment Q&A grounding score

Run offline
  pip install -e 'subrepos/theodore_drive_lab[test]'
  PYTHONPATH=subrepos/theodore_drive_lab/src:packages/shared/src \
    python3 -m pytest subrepos/theodore_drive_lab/tests -q
  PYTHONPATH=... uvicorn theodore_drive_lab.main:app --port 8096

APIs
  GET  /health
  GET|PATCH /api/drive/tuning (+ /preset/{name})
  POST /api/drive/wake/eval
  POST /api/drive/answer/eval
  POST /api/drive/bakeoff
  GET  /api/drive/champion
  GET  /api/drive/telemetry

Promote
  Champion wake/echo/pause knobs -> voiceCommands.ts + DriveModeScreen;
  TTS prefs -> speech gateway /tts defaults.
