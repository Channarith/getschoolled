Vision Agent Service — Webcam image recognition + xAI Grok voice agent
=======================================================================

Private sub-module for building and testing webcam-based teaching features:
  - Silhouette / body-presence detection (OpenCV MOG2, no extra model)
  - Face recognition + engagement (OpenCV YuNet + SFace via perception service)
  - User absence detection with debounced events and Theodore AI prompts
  - xAI Grok voice agent (Theodore persona) for solo and group classes
  - Server-Sent Events stream for real-time presence notifications

Port: 8006 (local)
Package: vision_agent
Service entry: services/vision_agent/src/vision_agent/main.py

Quick start
-----------
  # From repo root, with .venv active:
  cd services/vision_agent
  pip install -e '.[test]'
  PYTHONPATH=src uvicorn vision_agent.main:app --port 8006

  # Optionally wire the XAI Grok voice agent:
  export XAI_API_KEY=xai-...
  export XAI_MODEL=grok-2-1212
  export XAI_VISION_MODEL=grok-2-vision-1212

  # Optionally wire the perception service for face recognition:
  export VISION_MODE=local
  # (Models download on first request to ~/.cache/aoep/models)

Run tests
---------
  python3 -m pytest services/vision_agent/tests -q

Key environment variables
--------------------------
  XAI_API_KEY                     xAI API key (enables Theodore Grok voice agent)
  XAI_BASE_URL                    xAI API base URL (default https://api.x.ai/v1)
  XAI_MODEL                       Grok text model (default grok-2-1212)
  XAI_VISION_MODEL                Grok vision model (default grok-2-vision-1212)
  VISION_AGENT_ABSENCE_THRESHOLD_S  seconds before ABSENT fires (default 5.0)
  VISION_AGENT_RETURN_THRESHOLD_S   seconds of presence to confirm return (default 1.0)
  VISION_AGENT_MAX_SESSIONS       soft cap on concurrent sessions (default 200)
  VISION_MODE                     local | cloud (face recognition mode)
  VISION_MODEL_DIR                model weight cache dir (default ~/.cache/aoep/models)

Endpoints
---------
  POST   /sessions                  Create session (class_type, student_ids, lesson_title)
  GET    /sessions/{id}             Session status
  DELETE /sessions/{id}             End session
  POST   /sessions/{id}/frame       Process webcam frame (face + silhouette + presence)
  POST   /sessions/{id}/voice       Text query to Theodore (xAI Grok)
  POST   /sessions/{id}/frame-chat  Frame → Grok Vision → Theodore reaction
  GET    /sessions/{id}/events      SSE stream (absence_start, absence_end, ...)
  GET    /sessions/{id}/metrics     Cumulative engagement metrics
  GET    /capabilities              Probe available features
  GET    /health                    Health check
  GET    /version                   Service version

Session class types
-------------------
  solo    One student + Theodore AI (self-study or private tutoring)
  group   Multiple students; each tracked independently; group events aggregated

Presence states
---------------
  warming_up          Background model stabilising (first ~15 frames)
  present_face        Face detected; full engagement tracking active
  present_silhouette  Body visible but no face (user looking away / far from camera)
  absent              Neither face nor silhouette detected for >= ABSENCE_THRESHOLD_S

SSE event kinds
---------------
  connected               Stream connected
  absence_start           User went absent
  absence_end             User returned
  theodore_absence_prompt Theodore's AI-generated invite-back text
  voice_response          Theodore's reply to a student query
  session_ended           Session deleted via DELETE /sessions/{id}
