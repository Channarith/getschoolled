Theodore Webcam Lab (private-ready subproject)
==============================================

Purpose
-------
This subproject isolates webcam-recognition and natural voice-agent prototyping
for Theodore AI teaching and self-teaching flows, without changing production
classroom services.

Feature scope
-------------
- Solo and group class webcam evaluation
- Silhouette detection
- Learner absence detection with grace periods
- xAI voice-agent response integration (OpenAI-compatible API), plus local
  fallback when keys/network are unavailable
- 26-language voice-agent support for multilingual teaching
- Webcam-audio transcript absorption for answer understanding + feedback
- Webcam reinforcement games/challenges scored from live signals:
  focus streak, confidence smile, and integrity guard
- Group-lesson student window monitoring with per-student intervention severity
  and lesson alerts/messages for missing or cheating learners
- Live quality metrics + chart-ready series for every student window (distance,
  light, image quality, expression/behavior, mic quality, noise filtering)

API highlights
--------------
- POST /api/theodore/webcam/evaluate
- GET  /api/theodore/webcam/live-metrics/{session_id}
- GET  /theodore/webcam/live-monitor/{session_id}
- POST /api/theodore/voice/respond
- GET  /api/theodore/voice/languages
- POST /api/theodore/voice/ask-question
- POST /api/theodore/voice/absorb-audio-answer
- POST /api/theodore/webcam/games/challenge
- POST /api/theodore/webcam/games/attempt

Run locally
-----------
1) From repo root, activate the project venv:
   . .venv/bin/activate
2) Start lab API:
   PYTHONPATH=subrepos/theodore_webcam_lab/src python3 -m uvicorn theodore_webcam_lab.main:app --port 8310
3) Run tests:
   python3 -m pytest subrepos/theodore_webcam_lab/tests -q
