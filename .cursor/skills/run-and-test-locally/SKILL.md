---
name: run-and-test-locally
description: How to run the Salareen/AOEP stack locally (backend services + Next.js web + Expo mobile), run the test suites, and satisfy the CI gates before merging. Use when starting the app, reproducing a bug, running or adding pytest/ruff/typecheck/build, wiring the web to a backend, or checking "will CI pass". Covers the mandatory venv, service ports, and non-obvious gotchas (stale processes on ports, mobile version test-clobber, missing web deps).
---

# Run & test locally

## Backend
- **Always activate the venv first:** `. .venv/bin/activate` (system Python 3.12).
  `packages/shared` is editable-installed, so source edits are picked up without
  reinstalling; adding a NEW dependency requires re-running the install.
- Run a single service (loads `config/local.env`): `make run-identity` (:8008),
  `make run-memory` (:8004), `make run-orchestrator` (:8000). Or directly:
  `cd services/<svc> && PYTHONPATH=src:../../packages/shared/src python3 -m uvicorn <pkg>.main:app --port <port>`
  (speech pkg is `speech_gw`). **Restart identity after pulling auth/seed changes.**
- Full local stack (all services + web): `scripts/dev_up.sh` / `make dev-all`
  (`dev-down`, `dev-status` too). `infra/compose` is the containerized alternative
  (Docker is NOT preinstalled here).

## Web (Next.js, apps/web)
- `cd apps/web && pnpm install` then `pnpm run dev` (port 3000). It reads backend
  URLs from `NEXT_PUBLIC_*_URL` (e.g. `NEXT_PUBLIC_ORCHESTRATOR_URL`, default
  `http://localhost:8000`). Start the backend first.
- Use pnpm. It warns it ignored the `unrs-resolver` build script — safe; do NOT
  run interactive `pnpm approve-builds`.

## Mobile (Expo, apps/mobile)
- `pnpm install` then `pnpm typecheck`. `apps/mobile/src/config.ts` points at the
  cloud origin by default; use `MOBILE_DEPLOY_MODE=local` for local services.

## Tests & CI gates (what must be green to merge)
CI (`.github/workflows/ci.yml`) runs: **python** (pytest), **web** (`npm run
typecheck` + `npm run build`), **compose** (kustomize/compose config), **k8s**.
- Backend: `python3 -m pytest packages/shared/tests services/*/tests apps/agent-runtime/tests training/tests scripts/tests qa/tests -q`.
  Each service has `tests/conftest.py` that puts its `src` on `sys.path`; you can
  also run per-service from its dir. `make test` runs all.
- Lint: `ruff check packages/shared/src services/*/src qa training` (gated by
  `qa.yml`, not `ci.yml`). Keep touched files ruff-clean.
- Web: `cd apps/web && pnpm run typecheck && pnpm run build`. If typecheck/build
  fails on missing modules (`@playwright/test`, `livekit-client`), your local
  `node_modules` is stale — run `pnpm install` (CI installs fresh).

## Non-obvious gotchas (verified)
- **Stale processes on ports:** a previous session may still hold 8000/8002/8008/3000
  with OLD code (you'll get 404s or `EADDRINUSE`). Confirm with `curl :<port>/version`;
  kill by specific PID (`kill $(lsof -ti :<port>)`) — NEVER `pkill -f`. Firecracker
  networking means some listeners aren't visible to `lsof`; run on a different port
  if you can't reclaim it.
- **Mobile version files get clobbered by a test.** Running the full pytest suite
  executes `scripts/tests/test_bump_pr_version.py`, which writes the REAL
  `apps/mobile/{app.json,package.json,src/version.ts}` (to `0.3.82`). After a full
  suite run, `git checkout -- apps/mobile/app.json apps/mobile/package.json apps/mobile/src/version.ts`
  before committing.
- Face-recognition tests fetch a small dataset and **skip** if network is blocked —
  a green run may mean "skipped"; check the summary.
