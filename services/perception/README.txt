perception service (AOEP / Salareen)
====================================

Purpose
  Consent-gated face recognition and engagement/attention signals for the
  camera-aware classroom. Real, self-hosted on CPU via OpenCV YuNet (detect) +
  SFace (embed) through the aoep_shared VisionProvider.

Package / entrypoint
  perception  ->  services/perception/src/perception/main.py
Port
  8003 (local dev; :8000 in Docker/k8s)

Key endpoints
  POST /enroll/{student_id}          POST /identify
  POST /enroll-embedding/{student_id} POST /identify-embedding
  POST /analyze/consent-check        GET  /gallery
  GET  /vision/models/{name}
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  ./scripts/run_local_service.sh perception
  # or: cd services/perception && PYTHONPATH=src uvicorn perception.main:app --port 8003

Test
  cd services/perception && PYTHONPATH=src python -m pytest   # or: make test

Notes
  - Model weights are NOT in the repo. They download at runtime to
    VISION_MODEL_DIR (default ~/.cache/aoep/models) from the OpenCV Zoo.
  - Face-recognition tests fetch a small real dataset and SKIP cleanly when that
    network is blocked, so a green run may mean "skipped" — check the summary.
  - Vision deps live in requirements-dev.txt and the aoep-shared[vision] extra.

See also: AGENTS.md (perception/vision notes), docs/architecture.txt.
