Theodore Webcam Lab (private subproject)
=======================================

Purpose
  Isolated build-and-test surface for webcam image-recognition classroom features
  before production rollout. This lab focuses on:
  - solo and group class monitoring,
  - silhouette detection,
  - user absence / return detection,
  - Theodore natural voice-response hooks through xAI voice agents.

Layout
  src/theodore_webcam_lab/models.py    request/response contracts
  src/theodore_webcam_lab/monitor.py   class-mode monitoring logic
  src/theodore_webcam_lab/voice.py     xAI conversational voice adapter
  src/theodore_webcam_lab/api.py       FastAPI lab endpoints for integration tests
  tests/                               focused unit/API tests

Run tests
  . .venv/bin/activate
  python3 -m pytest private_subrepos/theodore_webcam_lab/tests -q

Environment variables (optional)
  XAI_API_KEY      xAI API key for live agent responses
  XAI_BASE_URL     defaults to https://api.x.ai/v1
  XAI_MODEL        defaults to grok-2-latest
