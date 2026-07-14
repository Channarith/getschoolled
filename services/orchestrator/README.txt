orchestrator service (AOEP / Salareen)
======================================

Purpose
  The "Teaching Director" / teaching brain the web + mobile apps call. Owns
  class sessions and the Tutor Q&A loop, the Salareen live rooms (LiveKit grid,
  Q&A speaking mutex, gifts/reactions, moderation) and their lifecycle
  (auto start / advance / end), scheduled group classes and solo 1:1 rooms, the
  training/cognitive agent APIs, assessment (adaptive quiz/grade), and the
  human-in-the-loop (HIL) review queue.

Package / entrypoint
  orchestrator  ->  services/orchestrator/src/orchestrator/main.py
Port
  8000 (local dev; :8000 in Docker/k8s too)

Key endpoints
  GET  /api/lessons
  POST /api/sessions            POST /api/sessions/{id}/advance|ask
  /api/live-rooms/*             (join, ask, chat, tick, start-presentation,
                                 advance, media-token, solo, gifts, reactions)
  /api/group-classes/*          (schedule, {id}/start, register, calendar.ics)
  /api/training/*  /api/cognitive/*  /api/agents/roster
  /director/plan   /assessment/quiz|grade   /api/hil/*
  Plus the shared /health /version /__meta /metrics /telemetry/* routes.

Run (local)
  make run-orchestrator                     # loads config/local.env
  # or manual:
  cd services/orchestrator && DEPLOY_MODE=local \
    CURRICULUM_DIR=/workspace/sample-curriculum \
    PYTHONPATH=src uvicorn orchestrator.main:app --port 8000

Test
  cd services/orchestrator && PYTHONPATH=src python -m pytest   # or: make test

Notes
  - Offline-first: with no LLM endpoint the Tutor returns a deterministic answer
    grounded in the retrieved RAG passages, so the demo works with no GPU/keys.
  - Live rooms mint real LiveKit tokens when a media server / LiveKit Cloud is
    configured (LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET); run a local
    server with `make run-livekit` (:7880).
  - The AI answers each learner in the language on their profile/device.

See also: .cursor/skills/live-rooms-video, .cursor/skills/backend-service,
docs/architecture.txt, docs/api-reference.txt.
