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

Run locally
-----------
1) From repo root, activate the project venv:
   . .venv/bin/activate
2) Start lab API:
   PYTHONPATH=subrepos/theodore_webcam_lab/src python3 -m uvicorn theodore_webcam_lab.main:app --port 8310
3) Run tests:
   python3 -m pytest subrepos/theodore_webcam_lab/tests -q
