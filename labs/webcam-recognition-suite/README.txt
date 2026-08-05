Webcam recognition lab (private)
================================

Purpose
  Build and test webcam image recognition for Salareen solo (1:1) and group
  classes — Theodore (AI) teaching and user self-teaching — plus silhouette
  detection, user-absence holds, and xAI Grok voice agents for natural speech.

This is a PRIVATE sub-repo under labs/. See PRIVATE.txt.

Capabilities exercised here
  1. Face-based recognition signals (hybrid embedding path; YuNet+SFace when
     OpenCV models are available).
  2. Body silhouette / person presence (HOG when OpenCV is present; synthetic
     detector for offline CI).
  3. Fused absence policy (face + silhouette) matching live-room grace/hold.
  4. Teaching modes: theodore_teach | self_teach (human hosts; Theodore assists).
  5. xAI Voice Agent API client (wss://api.x.ai/v1/realtime) with an offline
     mock so tests never need XAI_API_KEY.

Layout
  src/webcam_recognition_suite/     lab package
  tests/              offline pytest suite (no network required)
  scripts/run_lab.py  one-shot offline demo harness
  pyproject.toml      installable as webcam-lab (private)

Install (from monorepo root, venv active)
  pip install -e 'packages/shared[vision]'
  pip install -e labs/webcam-recognition
  # or without vision extras — silhouette mock + fusion still run:
  pip install -e labs/webcam-recognition

Run tests
  cd labs/webcam-recognition && PYTHONPATH=src:../../packages/shared/src \
    python3 -m pytest -q

Run offline lab demo
  python3 labs/webcam-recognition/scripts/run_lab.py
  python3 labs/webcam-recognition/scripts/run_lab.py --mode self_teach --size 6

Env (optional live voice)
  XAI_API_KEY=...          # server-side only; never ship to browsers
  XAI_VOICE_MODEL=grok-voice-latest
  XAI_VOICE_NAME=eve
  XAI_VOICE_WS_URL=wss://api.x.ai/v1/realtime

Promotion path
  Stable silhouette + presence fusion promote into aoep_shared.vision.silhouette
  and live-room presence_report. Voice agent client promotes into speech_gw /
  agent-runtime once keys and ephemeral tokens are wired in prod.
