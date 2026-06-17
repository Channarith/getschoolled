# AGENTS

Project conventions (from docs/cloud-agent-task.txt): plain-text/code only (no
new markdown beyond this operational file), always `python3`, dual-mode via env
(no code forks), pin dependency versions, update CHANGELOG.txt on meaningful
changes.

## Cursor Cloud specific instructions

Monorepo for the Agentic Online Education Platform. Backend = Python/FastAPI
behind a provider abstraction (`packages/shared`); frontend = Next.js
(`apps/web`). The dev loop runs services natively; `infra/compose` is for the
full containerized stack.

Environment / setup caveats (non-obvious):
- The update script creates `.venv` (system Python 3.12; the repo's
  `.python-version` requests 3.11 but it is not installable offline here — 3.12
  is compatible). Creating a venv requires the `python3.12-venv` apt package,
  which is not guaranteed preinstalled; the update script installs it.
- Activate the venv before any backend work: `. .venv/bin/activate`. Editable
  installs of `packages/shared` mean source edits are picked up without
  reinstalling; adding new dependencies requires re-running the install.
- Web uses pnpm. `pnpm install` warns it ignored the `unrs-resolver` build
  script; this is safe — lint/typecheck/build all pass without approving it. Do
  not run the interactive `pnpm approve-builds`.

Running things (see Makefile for the canonical targets):
- Backend tests: per-package/per-service `python -m pytest` (each service has a
  root `conftest.py` so `import app.*` resolves; run pytest from the service
  dir). `make test` runs them all.
- Orchestrator API (the teaching brain the web app calls): from
  `services/orchestrator`, `uvicorn app.main:app --port 8000`. Set
  `DEPLOY_MODE=local` and `CURRICULUM_DIR=/workspace/sample-curriculum`.
- Web dev server: `cd apps/web && pnpm run dev` (port 3000). It reads the
  orchestrator URL from `NEXT_PUBLIC_ORCHESTRATOR_URL` (defaults to
  http://localhost:8000). Start the orchestrator first.
- Config contracts live in `config/local.env` / `config/cloud.env`. Blank
  per-component overrides (e.g. `LLM_MODE=`) intentionally mean "inherit
  `DEPLOY_MODE`"; the Settings model normalizes blank to unset.

Docker / compose:
- Docker is NOT preinstalled in this environment, so `docker compose config`
  (the `compose` CI job / `make compose-config`) cannot run here. The compose
  YAML is structurally valid; install Docker if you need to exercise the full
  containerized stack.

Stubs vs real backends:
- In local mode the heavy providers (LLM, speech, vision, payments) are
  deterministic offline stubs so the end-to-end teaching loop runs without
  GPU/network/keys. Cloud implementations raise `CloudProviderUnavailable`
  until real endpoints/credentials are wired. Swapping is by env only.
