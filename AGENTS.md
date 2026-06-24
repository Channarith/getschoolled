# AGENTS

Project conventions (from docs/cloud-agent-task.txt): plain-text/code only (no
new markdown beyond this operational file), always `python3`, dual-mode via env
(no code forks), pin dependency versions, update CHANGELOG.txt on meaningful
changes.

Merge-conflict policy (keeps the auto-push into main flowing): conflicts in the
two high-churn docs auto-resolve instead of blocking a merge. This is wired via
`.gitattributes` merge drivers — run `make git-setup` (or `./scripts/setup-git.sh`)
once per clone/CI runner that performs a local merge, then merge as usual:
- `CHANGELOG.txt` -> `union` (built-in): keep BOTH sides' appended entries; also
  honored by GitHub's server-side merge.
- `README.md` -> `theirs` (custom driver): accept the INCOMING (theirs) version.
  Custom drivers run only on local merges; GitHub's server-side PR merge does not
  execute them, so README conflicts in PR auto-merge need a local merge with the
  driver configured. When a local merge is impractical, default to accepting the
  incoming branch's `README.md`/`CHANGELOG.txt` and re-running the README cleanup.

## Push-to-main checklist (required every time main is updated)

1. CHANGELOG.txt: prepend a **dated** entry (`- YYYY-MM-DD - …`, newest first)
   for the change. CHANGELOG uses a union merge driver (.gitattributes) so
   concurrent entries auto-combine - keep one dated bullet per change.
2. **Release version (required on every PR to main):** run
   `python3 scripts/bump_pr_version.py` before merge. This advances `VERSION`,
   `build-info.txt`, and `apps/web/app/lib/version.ts` (and web `package.json`).
   CI fails PRs that do not bump VERSION vs `main`. Patch bump by default;
   minor when more than 8 pending changelog entries have accumulated.
3. README.md: review and clean it up - remove legacy/unsupported/redundant
   wording, fix stale references (ports, paths, removed features), and ensure
   there are NO duplicate sections (e.g. a single `## Brand`). The README must
   reflect the current shipped state, not historical merges.
4. UI changes: capture FRESH artifacts every time the UI changes - screenshots
   into `docs/screens/` and a short video walkthrough into `docs/demos/` - and
   reference the current ones from the README "Screens and videos" section.
   Replace stale screenshots/videos rather than accumulating outdated ones.

## Cursor Cloud specific instructions

Single canonical stack: shared lib is `aoep_shared` (in `packages/shared`,
distribution `aoep-shared`); every service uses a `src/` layout
(`services/<name>/src/<pkg>/main.py`) and depends on `aoep_shared`. (The older
`eduplatform_shared` + `services/*/app/` duplicate has been removed.) Service
package names match the service except speech, whose package is `speech_gw`.

Face recognition (perception service): real, self-hosted via OpenCV YuNet +
SFace (CPU; `aoep_shared.vision`). Model weights are NOT in the repo — they
download at runtime to `VISION_MODEL_DIR` (default `~/.cache/aoep/models`) from
the OpenCV Zoo on GitHub. The face-recognition tests fetch a small real dataset
(`ageitgey/face_recognition` knn examples) into a cache and **skip** cleanly if
that network is blocked, so a green run may mean "skipped" — check the summary.
Perception's vision deps (`opencv-contrib-python-headless`, `onnxruntime`,
`numpy`) are in `requirements-dev.txt` and the `aoep-shared[vision]` extra.

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
- Backend tests: per-package/per-service `python -m pytest` run from the service
  dir (each service has a `tests/conftest.py` that puts its `src` on `sys.path`).
  `make test` runs them all.
- Orchestrator API (the teaching brain the web app calls, on `/api/lessons`,
  `/api/sessions`, `/api/sessions/{id}/advance|ask`): from
  `services/orchestrator`, `PYTHONPATH=src uvicorn orchestrator.main:app --port 8000`.
  Set `DEPLOY_MODE=local` and `CURRICULUM_DIR=/workspace/sample-curriculum`.
  The local LLM provider targets a real vLLM/Ollama endpoint; with none
  configured, the Tutor falls back to a deterministic answer grounded in the
  retrieved RAG passages, so the demo works offline.
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
- Heavy providers (LLM/speech serving) target real endpoints; without them the
  network paths raise `NotImplementedError`. The offline-usable pieces (RAG,
  vision/face recognition, sandbox payments, adaptive/assessment logic, the
  Tutor's grounded fallback) keep the end-to-end teaching loop working without
  GPU/network/keys. Local vs cloud selection is by env only (no code forks).
