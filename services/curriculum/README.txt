curriculum service (AOEP / Salareen)
====================================

Purpose
  The content plane: course catalog + search/facets, the RAG corpus, decks /
  courses / programs, content ingest, audio courses (Drive Mode), jobs/careers,
  recommendations, scenes, validation/scoring, notifications feed, and the HTTP
  homework APIs (the offline homework library lives in aoep_shared.homework and
  services/homework).

Package / entrypoint
  curriculum  ->  services/curriculum/src/curriculum/main.py
Port
  8005 (local dev; :8000 in Docker/k8s)

Key endpoints
  /courses/*  /decks/*  /catalog  /home  /learn/*  /recommend
  /audio/courses  /jobs/*  /scenes/*  /validate/*  /scoring/*
  /ingest/*  /homework/*  /notifications/feed
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  ./scripts/run_local_service.sh curriculum
  # or: cd services/curriculum && DEPLOY_MODE=local \
  #       PYTHONPATH=src uvicorn curriculum.main:app --port 8005

Test
  cd services/curriculum && PYTHONPATH=src python -m pytest   # or: make test

Notes
  - CURRICULUM_DIR points at bundled lessons (default sample-curriculum/).
  - Content packs under aoep_shared/data/content_packs/ (+ AOEP_CONTENT_PACKS)
    grow the catalog with no code change.

See also: .cursor/skills/harvester-content, docs/api-reference.txt.
