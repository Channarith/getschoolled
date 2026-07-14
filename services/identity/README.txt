identity service (AOEP / Salareen)
==================================

Purpose
  Accounts and auth (sessions, 2FA, OAuth/passkeys), membership/VIP tiers, the
  Netflix-style onboarding wizard, learner sub-profiles (students), enrollments,
  the points/rewards ledger + prize catalog, the mini-games arcade, portfolio,
  profile-context sharing, and the learner's preferred language. System of
  record backed by a Redis snapshot (durable across replicas/redeploys).

Package / entrypoint
  identity  ->  services/identity/src/identity/main.py
Port
  8008 (local dev; :8000 in Docker/k8s)

Key endpoints
  /auth/*  (signup, login, me, password, 2fa, oauth)   /account/language
  /onboarding/*   /membership/*   /students/*   /enrollments
  /rewards/*   /games/*   /portfolio   /profile-shares/context
  /language/practice   /admin/*
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  make run-identity                 # loads config/local.env (seeds admin + QA)
  # or: cd services/identity && PYTHONPATH=src uvicorn identity.main:app --port 8008

Test
  cd services/identity && PYTHONPATH=src python -m pytest    # or: make test

Notes
  - Restart identity after pulling auth/seed changes.
  - preferred_language (POST /account/language, returned by /auth/me) follows a
    learner across devices so web + mobile show their language and the AI answers
    in it.
  - Admin/flags features are gated by ADMIN_SECRET.

See also: .cursor/skills/identity-rewards-durability.
