apps/web — Salareen web app (Next.js 14)
========================================

Purpose
  The primary web UI: live class + Salareen live rooms, Drive Mode, catalog /
  browse, onboarding + billing, rewards/arcade, careers, admin, our-story, and
  the training surfaces. The same UI runs against local or cloud backends.

Backend URLs
  Resolved in apps/web/app/lib/api.ts. Local dev uses per-service ports
  (orchestrator :8000, curriculum :8005, identity :8008, ...); deployed it uses
  same-origin path prefixes (/orchestrator, /identity, ...) via the gateway.
  Override with NEXT_PUBLIC_<SERVICE>_URL (e.g. NEXT_PUBLIC_ORCHESTRATOR_URL).

Run (dev)
  cd apps/web && pnpm install && pnpm run dev        # http://localhost:3000
  (start the orchestrator on :8000 first for the class/live-room pages)

Checks
  pnpm run typecheck      # tsc --noEmit          (make web-typecheck)
  pnpm run lint           # next lint
  pnpm run build          # production build       (make web-build)
  pnpm run e2e            # Playwright end-to-end

Notes
  - Uses pnpm. The unrs-resolver postinstall warning is safe to ignore; do NOT
    run the interactive `pnpm approve-builds`.
  - i18n lives in app/lib/i18n.tsx (+ i18n-strings.ts). The signed-in learner's
    language is adopted from and saved to their account.

See also: README.md (Setup / Run commands), .cursor/skills/run-and-test-locally.
