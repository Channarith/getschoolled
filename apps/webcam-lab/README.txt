apps/webcam-lab — PRIVATE webcam recognition + xAI voice lab (Salareen)
=======================================================================

PRIVATE INTERNAL SUB-PACKAGE — build and test only. Not exposed on public
ingress by default. Promote proven pieces into perception / orchestrator /
web live-room after lab validation.

Purpose
  Isolated workspace to build and test webcam image recognition for:
  - Solo classes (Theodore AI teaches one learner)
  - Group classes (Theodore hosts a small room)
  - Self-teaching (learner leads; xAI voice agent coaches)
  with silhouette detection, user-absence tracking, and xAI Grok Voice Agents
  for natural speech-to-speech conversation.

Distribution
  aoep-webcam-lab
Entrypoint
  python3 -m webcam_lab.main
  (uvicorn on :8011 by default; WEBCAM_LAB_PORT overrides)

Capabilities exercised here
  - Face + silhouette frame analysis (aoep_shared.vision)
  - Absence / presence-hold state machine
  - xAI ephemeral token mint + Theodore / self-teach session configs
  - Lab session store for solo / group / self_teach modes

Env
  XAI_API_KEY          optional; blank => mock ephemeral tokens
  XAI_VOICE_MODEL      default grok-voice-latest
  XAI_VOICE_ID         default eve
  WEBCAM_LAB_PORT      default 8011
  VISION_MODEL_DIR     optional; when set + opencv installed, real YuNet path

Test
  cd apps/webcam-lab && PYTHONPATH=src:../../packages/shared/src \
    python3 -m pytest tests -q
  (also wired into `make test` via apps/webcam-lab/tests)

See also
  docs/webcam-lab.txt
  .cursor/skills/live-rooms-video, speech-tts, platform-architecture
