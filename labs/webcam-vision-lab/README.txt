WEBCAM VISION LAB — private sub-repo for Theodore teaching presence R&D
=======================================================================

Purpose
  Isolated sandbox to build and test webcam image recognition for solo and
  group classes: Theodore (AI) teaching, user self-teaching, silhouette UI
  states, user absence detection, and xAI Grok voice-agent responses.

  This lab is designed to be extracted as a PRIVATE GitHub repository (see
  SUBREPO.txt) while staying editable inside the AOEP monorepo during R&D.

What lives here
  src/webcam_vision_lab/
    presence/     silhouette + absence tracking (mirrors live-room policy)
    voice/        xAI Grok realtime voice agent client + Theodore personas
    scenarios/    solo 1:1, group class, self-teach fixtures
    harness/      CLI demos + integration runner against local AOEP services

Quick start (inside monorepo)
  cd labs/webcam-vision-lab
  python3 -m venv .venv && . .venv/bin/activate
  pip install -e ../../packages/shared
  pip install -e ".[dev]"
  python3 -m pytest tests/ -q

  # Presence classification demo (no camera — uses synthetic signals)
  python3 -m webcam_vision_lab.harness.run_presence_demo

  # xAI voice agent session config (no network — prints Theodore persona)
  python3 -m webcam_vision_lab.harness.run_voice_demo --dry-run

  # Integration harness against local orchestrator + perception (optional)
  python3 -m webcam_vision_lab.harness.integration_harness --check-only

Environment (copy config/lab.env.example -> config/lab.env)
  XAI_API_KEY              xAI API key for Grok voice agent (server-side only)
  ORCHESTRATOR_URL         default http://localhost:8000
  PERCEPTION_URL           default http://localhost:8003
  WEBCAM_LAB_MODE          solo | group | self_teach

Relationship to production code
  - Face detection + embedding: aoep_shared.vision (YuNet + SFace) and the
    web hybrid path (apps/web/app/lib/vision.ts).
  - Live-room presence holds: packages/shared/src/aoep_shared/live_room.py
    report_presence() + PresencePolicy.
  - Silhouette overlay UI: apps/web/app/live-room/[roomId]/page.tsx
  - This lab exercises the SAME policy semantics offline so R&D does not
    require a full live class to iterate.

See also: SUBREPO.txt, docs/architecture.txt (perception service), AGENTS.md.
