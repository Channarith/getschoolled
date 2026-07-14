integrations service (AOEP / Salareen)
======================================

Purpose
  The connectivity hub: signed outbound webhooks + inbound provider webhooks,
  payment webhooks, LMS/LTI/OneRoster/AGS, cloud notify / calendar / OIDC-SSO,
  finance payout + entitlement hooks, the Zoom/Teams/Meet meeting bridges, and
  an internal-auth-gated API client registry.

Package / entrypoint
  integrations  ->  services/integrations/src/integrations/main.py
Port
  8007 (local dev; :8000 in Docker/k8s)

Key endpoints
  /webhooks/subscriptions  /webhooks/emit  /webhooks/inbound/{provider}
  /payments/webhook/{provider}   /lms/*
  /bridges/*  (Zoom / Teams / Meet)   /notify   /calendar/schedule   /sso/oidc
  /finance/payout   /entitlements/{customer}   /clients
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  ./scripts/run_local_service.sh integrations
  # or: cd services/integrations && PYTHONPATH=src \
  #       uvicorn integrations.main:app --port 8007

Test
  cd services/integrations && PYTHONPATH=src python -m pytest   # or: make test

Notes
  - Connectors use mock adapters offline (aoep_shared/connectors/*); real
    providers activate by env. Salareen's own LiveKit rooms live in the
    orchestrator; Zoom/Teams/Meet here are separate bridges.

See also: docs/integrations-jobs-careers.txt, docs/api-reference.txt.
