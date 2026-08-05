labs/webcam-recognition — private webcam recognition lab (AOEP / Salareen)
==========================================================================

Purpose
  Private build-and-test sub-project for webcam image recognition used in
  solo and group classes. Covers Theodore (AI) teaching, learner self-teaching,
  silhouette detection, user-absence holds, and natural voice replies via
  xAI Grok Voice Agents (Speech-to-Speech realtime API).

This is intentionally isolated under labs/ so it can be developed and tested
without touching production live-room paths until the signals are proven.
Promote proven pieces into aoep_shared.vision + apps/web live-room presence.

Scope
  - Face / silhouette / absence presence pipeline (CPU OpenCV)
  - Solo class + group class session harness
  - Theodore AI host mode + self-teach mode
  - xAI voice agent client (wss://api.x.ai/v1/realtime) with offline mock
  - Presence report shape compatible with orchestrator /presence-report
  - Local FastAPI lab server + webcam HTML harness

Package / entrypoint
  webcam_lab  ->  labs/webcam-recognition/src/webcam_lab/
  CLI:          python3 -m webcam_lab
  Lab server:   python3 -m webcam_lab.server   (default :8093)

Environment
  XAI_API_KEY          xAI API key for live Grok Voice Agents (optional)
  XAI_VOICE_MODEL      default grok-voice-latest
  XAI_VOICE_ID         built-in voice id (default eve)
  WEBCAM_LAB_PORT      lab HTTP port (default 8093)
  VISION_MODEL_DIR     optional YuNet/SFace cache (reuse AOEP cache)

Install (editable, from repo root)
  pip install -e 'labs/webcam-recognition[vision,voice,server,test]'

Test
  cd labs/webcam-recognition && PYTHONPATH=src python3 -m pytest -q

Extract as a private GitHub repo
  ./scripts/extract_private_repo.sh Channarith/webcam-recognition-lab
  (creates a fresh private repo from this tree; keeps history optional)

Privacy
  Consent-gated. Raw frames stay on-device / in the lab process. Only presence
  summaries (present, face_count, silhouette, liveness, reason) leave the lab.
  See docs/PRIVACY.txt.

See also
  services/perception, packages/shared/src/aoep_shared/vision,
  apps/web/app/live-room (presence probe), docs/live-rooms-video skill.
