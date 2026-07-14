memory service (AOEP / Salareen)
================================

Purpose
  Learner state and platform policy: consent records, legal/compliance notices
  and regional policy, feature flags, surveys, mascot resolution, and the
  mastery/behavior learning signals the adaptive loop reads and writes.

Package / entrypoint
  memory  ->  services/memory/src/memory/main.py
Port
  8004 (local dev; :8000 in Docker/k8s)

Key endpoints
  /consent   /legal/notices  /legal/accept   /compliance/{region}
  /flags/*   /survey/*   /mascots/*
  /mastery   /behavior   /learner/{student_id}/{topic}   /retention/purge
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  make run-memory
  # or: cd services/memory && PYTHONPATH=src uvicorn memory.main:app --port 8004

Test
  cd services/memory && PYTHONPATH=src python -m pytest    # or: make test

Notes
  - Feature flags behind /flags/* are gated by ADMIN_SECRET (see the
    identity-rewards-durability skill).

See also: .cursor/skills/identity-rewards-durability, docs/api-reference.txt.
