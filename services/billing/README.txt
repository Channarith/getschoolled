billing service (AOEP / Salareen)
=================================

Purpose
  Plans and entitlements, the "can this learner start?" gate, payment methods
  and checkout, and ad slots / inventory / revenue. Payment logic (50 methods
  across 13 processors) lives in aoep_shared.payments; ads in aoep_shared.ads*.

Package / entrypoint
  billing  ->  services/billing/src/billing/main.py
Port
  8006 (local dev; :8000 in Docker/k8s)

Key endpoints
  /plans   /entitlements/can-start
  /payment-methods   /payment-methods/by-country   /checkout
  /ads/networks   /ads/slot/{slot_id}   /ads/impression   /ads/revenue
  Plus /health /version /__meta /metrics /telemetry/*.

Run (local)
  ./scripts/run_local_service.sh billing
  # or: cd services/billing && PYTHONPATH=src uvicorn billing.main:app --port 8006

Test
  cd services/billing && PYTHONPATH=src python -m pytest    # or: make test

Notes
  - Local/sandbox payment paths work with no processor keys; cloud paths route
    to real processors by env. Ad networks selected via AD_NETWORK.

See also: docs/payments.txt, docs/payments-and-security.txt.
