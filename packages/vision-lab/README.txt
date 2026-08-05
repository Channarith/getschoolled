AOEP Vision Lab
===============

Private-ready experimental package for webcam image recognition features that
support Theodore (AI) in solo lessons, group classes, and self-teaching flows.

Scope
-----
- Turn detector output from a webcam or synthetic frame replay into the live-room
  presence-report payload used by the orchestrator.
- Test silhouette/body-present signals separately from face identity so absence,
  camera misalignment, and too-many-faces cases are visible before they reach
  production UI.
- Exercise xAI/Grok OpenAI-compatible responses as speakable chunks that can be
  sent to the existing speech gateway or client TTS pipeline.
- Keep raw webcam pixels out of this package. Experiments should pass metadata
  such as face count, bounding boxes, attention/gaze scores, and silhouette
  confidence from an on-device detector.

Privacy model
-------------
This package is designed to be split or mirrored to a private repository without
changing production service code. Do not commit raw webcam captures, biometric
embeddings, model weights, or learner media here. Use synthetic observations in
tests and local-only files under ignored output directories for manual trials.

Local usage
-----------
Install from the repo root after the normal AOEP venv is active:

  python3 -m pip install -e packages/vision-lab[test]

Run the lab tests:

  python3 -m pytest packages/vision-lab/tests -q

Configure xAI for live experiments:

  export XAI_API_KEY=...
  export XAI_MODEL=grok-4-latest

The xAI client is transport-isolated so tests mock HTTP and never require a real
API key.
