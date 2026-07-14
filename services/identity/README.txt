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

Troubleshooting: "cloud unreachable at .../identity" (login fails in prod)
  This is a network/availability failure at the edge (both the mobile primary
  https://www.salareen.com/identity AND the Vultr-IP failover were exhausted) —
  NOT bad credentials (that returns 401). Identity itself needs no secret to run:
  AUTH_SIGNING_KEY, DEFAULT_ADMIN_PASSWORD, and ADMIN_SECRET all fall back to
  dev defaults, so seeded-admin login works even with aoep-secrets absent — but
  the Deployment mounts aoep-secrets via `envFrom: secretRef` (non-optional), so
  a MISSING aoep-secrets keeps the pods from starting. Diagnose in order:

    # 1) Are identity pods Ready? (CrashLoop / CreateContainerConfigError?)
    kubectl -n aoep get pods -l app=identity -o wide
    kubectl -n aoep logs deploy/identity --tail=100
    # CreateContainerConfigError -> aoep-secrets is missing (see step 4).

    # 2) Both ingresses present? aoep-apis owns the /identity route; if it's
    #    gone, /identity falls through to the web app (HTML, not JSON).
    kubectl -n aoep get ingress aoep aoep-apis
    kubectl -n aoep describe ingress aoep-apis | grep -A1 identity

    # 3) TLS valid for www.salareen.com? A failed cert = mobile TLS handshake
    #    fails = "unreachable".
    kubectl -n aoep get certificate salareen-tls
    curl -sS -o /dev/null -w "%{http_code}\n" https://www.salareen.com/identity/health
    curl -sS -o /dev/null -w "%{http_code}\n" http://45.63.91.80/identity/health   # failover base

    # 4) Is the secret present? Re-bootstrap (create-if-missing) then restart.
    kubectl -n aoep get secret aoep-secrets
    LIVEKIT_API_KEY=... LIVEKIT_API_SECRET=... bash scripts/k8s_bootstrap_secrets.sh
    kubectl -n aoep rollout restart deploy/identity && kubectl -n aoep rollout status deploy/identity

  A full deploy via scripts/deploy_vke.sh ensures aoep-secrets (create-if-missing)
  before applying manifests; a bare `kubectl apply -k` does NOT create it (it is
  managed out of band), so run the bootstrap once per fresh cluster.

See also: .cursor/skills/identity-rewards-durability, .cursor/skills/release-and-deploy,
scripts/k8s_bootstrap_secrets.sh, scripts/deploy_vke.sh.
