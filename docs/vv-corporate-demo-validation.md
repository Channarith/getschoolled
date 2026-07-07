# Corporate Training — Investor-Demo Validation Strategy

Companion to the platform-wide [master V&V plan](vv-master-plan.md) (test WV-22
covers the corporate funnel there). This document is the focused, executable
validation strategy for demoing **corporate training courses** to investors:
what the demo path is, what already protects it, what was fixed, what is now
automated, and what stays manual.

- Demo surfaces: web `/corporate`, `/corporate/learn`, `/jobs`; mobile `CareersScreen`.
- One-command gate: `make demo-check` (GO / NO-GO), see [§6](#6-demo-readiness-gate--make-demo-check).
- Presenter script: `scripts/PRESENTER_RUNBOOK.txt` (this doc covers validation, not stagecraft).

## 1. The demo journey

The exact investor click path, in order:

| # | Step | Route | Backing services |
|---|------|-------|------------------|
| J1 | Corporate catalog: 11 AI-led courses grouped AI / Data / Engineering + 4 seeded program tracks | `/corporate` | curriculum (`/programs`, `/courses/search`), orchestrator (`/api/lessons`) |
| J2 | Start course → locked auto-start player, slide 1 renders | `/corporate/learn?lesson=<id>` | orchestrator (sessions), browser TTS |
| J3 | Advance slides; AI teacher narration; pop quiz may appear | same | orchestrator, curriculum (quiz) |
| J4 | Ask the AI teacher a question → grounded answer | same | orchestrator (`_offline_answer` fallback, `services/orchestrator/src/orchestrator/teaching.py`) |
| J5 | Finish class → completion + reward points | same | identity (enrollments, rewards), memory (adaptation) |
| J6 | Careers: job list → job detail (coverage %, matched courses, skill gap) | `/jobs` | curriculum (`/jobs`, `/jobs/{id}`) |
| J7 | Paste a job description → parsed skills + course recommendations | `/jobs` | curriculum (`/jobs/parse`) |
| J8 | Mobile mirror of J6–J7 | mobile `CareersScreen` | same `/jobs` endpoints |

**Out of demo scope (not built — do not demo):** org signup, corporate-admin
role, seat provisioning/rostering, org billing, certificates, SSO/SCIM/LTI/xAPI.
The enterprise deck (`docs/vv-corporate-training-deck.html`) is aspirational.

## 2. What was fixed (demo blockers)

| Blocker | Fix | Where |
|---------|-----|-------|
| `/corporate` "Programs" section always empty (in-memory store, nothing seeded) | Startup seeding of 4 corporate tracks (AI Fluency for Teams, AI Engineering Upskilling, Data & Decisions, AI Leadership) grouping all 11 corporate lessons; idempotent, disable with `SEED_CORPORATE_PROGRAMS=0` | `services/curriculum/src/curriculum/corporate_programs.py`, hook in `main.py` |
| Program course entries linked to `/watch?course=` (dead for lessons) and rendered raw ids | Program cards resolve course ids against corporate lessons and deep-link to `/corporate/learn?lesson=`; "Start program" launches the track's first course | `apps/web/app/corporate/page.tsx` |
| "Assign to team" button dead-ended at the personal `/account` page | Retargeted to a sales-contact `mailto:` and relabeled "Talk to us about team seats" (honest — rostering is not built) | `apps/web/app/corporate/page.tsx`, `apps/web/app/lib/i18n-pages.ts` |
| `make qa` (qa/regression.py) silently skipped `services/identity/tests` (93 tests, the auth surface of this demo) and `qa/tests` (13) | Added both to `TEST_GLOBS`, aligning the gate with `make test` and CI | `qa/regression.py` |
| Native dev stack (`make dev-all`) loaded **zero lessons** — `config/local.env` carries the Docker container path `/app/sample-curriculum` for `CURRICULUM_DIR`, so the whole corporate catalog rendered empty on a natively-run demo machine (found by the demo-check probes) | `dev_up.sh` falls back to the repo's `sample-curriculum` when the configured dir doesn't exist on this host | `scripts/dev_up.sh` |
| Site-wide ~54 px horizontal scroll on phone-width viewports — the top nav is a non-wrapping flex row (found by CD-E5 responsive spec) | Nav wraps on narrow viewports (`flex-wrap: wrap`) | `apps/web/app/globals.css` |

## 3. Existing automated coverage leveraged

| Journey step | Existing protection |
|--------------|--------------------|
| J1 catalog data | orchestrator lesson-loader tests; curriculum catalog/search tests |
| J4 teaching Q&A | orchestrator teaching/groundedness tests (`test_teaching_api.py`, `test_groundedness_api.py`, `test_live_loop_e2e.py`) |
| J5 auth/enrollment/rewards | identity suite (93 tests — now actually run by `make qa`), `qa/tests/test_new_features_integration.py` cross-service flow |
| J6–J7 jobs matching | `services/curriculum/tests/test_jobs_api.py`, `test_skills_taxonomy_api.py` |
| Latency/robustness | `qa/stress.py` scenarios (orchestrator ask/sessions, curriculum catalog/search, identity signup/rewards) |

## 4. Gap analysis → disposition

| Gap | Disposition |
|-----|-------------|
| No test pinned the corporate lesson set or `audience` contract the web filter relies on | **AUTOMATED (new)** CD-B5/B6 |
| Nothing guaranteed programs are seeded / course ids resolve | **AUTOMATED (new)** CD-B1..B4, CD-B7 |
| Zero browser automation for any demo surface | **AUTOMATED (new)** Playwright CD-E1..E5 |
| Zero mobile automation | **MANUAL** CD-M1..M5 checklist now; Maestro is the master-plan follow-up |
| No single pre-demo go/no-go | **AUTOMATED (new)** `make demo-check` |
| AI teaching quality, audio feel, UX polish, rehearsal | **MANUAL** CD-X1..X4 charter |

## 5. Test inventory

### 5.1 Backend (pytest) — run in CI, `make qa`, and `make demo-check`

| ID | Test | File |
|----|------|------|
| CD-B1 | Seeding populates an empty store with 4 corporate tracks | `services/curriculum/tests/test_program_seeding.py` |
| CD-B2 | Seeding is idempotent; operator-authored programs win | same |
| CD-B3 | `GET /programs?audience=corporate` returns the seeded tracks | same |
| CD-B4 | Every seeded course id is a real corporate lesson, resolves via `/courses/search`, and the set covers all 11 | same |
| CD-B5 | `/api/lessons` exposes `audience` | `services/orchestrator/tests/test_corporate_lessons.py` |
| CD-B6 | The 11 corporate lesson ids + tracks are pinned; title/slides present | same |
| CD-B7 | `SEED_CORPORATE_PROGRAMS=0` disables seeding | `test_program_seeding.py` |

### 5.2 Web E2E (Playwright) — `cd apps/web && npm run e2e`

Suite: `apps/web/e2e/corporate/` against the real stack (no service mocks).
Auth: one UI login as the seeded QA learner (`global-setup.ts`), reused via
storage state. Browser TTS is stubbed (silent, but invocation asserted).

| ID | Spec | Asserts |
|----|------|---------|
| CD-E1 | `catalog.spec.ts` | 11 courses render with Start buttons; AI/Data/Engineering grouping; seeded programs visible (blocker-1 trap); team-seats CTA is a mailto (blocker-2 trap); no raw i18n keys; no console errors |
| CD-E2 | `learn.spec.ts` | Locked auto-start to slide 1 (no picker); slides advance with distinct content + narration; Q&A returns a grounded non-empty answer; TTS `speak` invoked |
| CD-E3 | `completion.spec.ts` | Finish class → completion banner + reward points + `/rewards` link + "take again" (delta-tolerant across re-runs) |
| CD-E4 | `jobs.spec.ts` | Job list renders; detail shows "cover N% of this role"; paste-JD (fixture) → catalog coverage + recommendations |
| CD-E5 | `i18n-responsive.spec.ts` | Spanish locale translates `/corporate`; `/corporate` + `/jobs` have no horizontal overflow at iPhone-12 viewport (runs in desktop + mobile-viewport projects) |

### 5.3 Mobile manual checklist (CD-M) — ~15 min, at demo rehearsal

Launch per `make mobile-setup` / Expo Go, backend reachable from device.

- CD-M1: App launches; Careers tab opens; job list loads.
- CD-M2: Open a job → coverage %, matched courses, skill gap render.
- CD-M3: Paste the fixture JD (`apps/web/e2e/fixtures/job-description.txt`) → parse result renders.
- CD-M4: Rotate device + scroll long lists — no clipped/overlapping UI.
- CD-M5: Airplane mode → jobs view degrades gracefully (sample board / clear error, no crash).

(Maestro automation for this screen is the post-demo follow-up per the master plan.)

### 5.4 Manual charter (CD-X) — human judgment, before demo day

| ID | What | Owner / when | Time |
|----|------|--------------|------|
| CD-X1 | AI teaching quality: run 2 corporate lessons end-to-end; check coherence, grounding of answers, quiz sanity. Rehearse the exact Q&A phrasings the presenter will use — offline answers are templated | content-savvy engineer, day before | 30 min |
| CD-X2 | Audio: narration on the **demo machine's** browser/voice — pacing, pronunciation of technical terms | presenter, demo machine | 10 min |
| CD-X3 | UX polish sweep at projector resolution: spacing, empty states, loading flashes, console errors on `/corporate`, learn, `/jobs` | any engineer | 20 min |
| CD-X4 | Timed full click-through of §1, per presenter runbook — day before AND morning of | presenter | 15 min × 2 |

## 6. Demo-readiness gate — `make demo-check`

`scripts/demo_check.py` produces a GO / NO-GO table (non-zero exit on NO-GO):

1. Targeted pytest subset (CD-B* + jobs API + cross-service integration) — minutes.
2. Stack probes: `/health` on orchestrator/memory/curriculum/identity + web; `GET /programs?audience=corporate` non-empty; ≥11 corporate lessons; jobs board returns postings from the **sample** provider (guards against accidental live-network dependence; `--allow-live-jobs` to override deliberately).
3. Playwright corporate suite (CD-E*).
4. Stress smoke: `qa/stress.py --smoke` with the stress SLA (error ≤1%, p95 ≤1500 ms, functional ≥99%). Note: `qa/loadtest.py`'s 300 ms p95 is a separate per-endpoint SLA, not this gate.

Flags: `--skip-e2e`, `--skip-stress`, `--skip-pytest`, `--json out.json`.

CI: run manually before demos; a nightly non-blocking workflow is the safe next
step. Do **not** make it a required PR check until it has a week of stability —
`automerge.yml` merges any green PR without human review, so a flaky required
E2E gate would either block all merging or breed false confidence. The ready
workflow lives at `docs/ci/demo-check.yml`; move it to
`.github/workflows/demo-check.yml` in a follow-up pushed with a `workflow`-scoped
token (this branch's token lacked that scope).

## 7. Demo-day runbook

### Environment

Two equivalent stacks; both are deterministic offline (no paid keys needed):

- **Native (recommended for the demo machine):** `make dev-all` → health summary; `make dev-status`; logs in `./logs/`. `config/local.env` defaults are already demo-safe (`JOBS_LIVE` empty → sample board, `SEED_CORPORATE_PROGRAMS=1`, `SEED_QA_ACCOUNTS=1`).
- **Compose:** `make up-e2e` (overlay `infra/compose/docker-compose.e2e.yml` pins `JOBS_PROVIDER=sample`, `JOBS_LIVE=0` — the base compose file defaults to live jobs).

| Env | Demo value | Why |
|-----|-----------|-----|
| `JOBS_LIVE` / `JOBS_PROVIDER` | unset / `sample` | offline, deterministic job board (cannot fail on venue Wi-Fi) |
| `SEED_CORPORATE_PROGRAMS` | `1` | programs section populated |
| `SEED_QA_ACCOUNTS` | `1` | demo login exists |
| `LLM_BASE_URL` etc. | unset (offline answers) or your endpoint | if set for the demo, rehearse CD-X1 **and** run `make demo-check` against that exact config |

### Boot sequence (morning of)

1. `make dev-all` (or `make up-e2e`) → all health green.
2. `make demo-check` → **GO**.
3. CD-X4 timed rehearsal.

### Accounts

- Demo learner: `qa-learner@salareen.com` / `QaTest123` (seeded, `services/identity/src/identity/bootstrap.py`; reseed via `POST /identity/admin/accounts/reseed-seeded`).
- Backup: `admin@salareen.com` / `DEFAULT_ADMIN_PASSWORD` (default `88888888`).
- **One-time dialogs:** a fresh (or freshly reseeded) account hits two modals on
  first signed-in use — the AI & consent disclaimer and the learning-profile
  survey. Log in once during rehearsal (CD-X4) on the demo browser profile to
  clear both, or budget for them in the script. Reseeding accounts or clearing
  browser storage brings them back.

## 8. Live contingency table

| If this fails on stage | Do this |
|------------------------|---------|
| Programs section empty | Restart the curriculum service (seeding is idempotent at startup); `make dev-status` to confirm |
| Jobs list empty/slow | Confirm sample provider (`curl :8005/jobs?limit=1` → `"source": "sample"`); sample board cannot hit the network |
| Q&A answer weak/wrong | Offline answers are retrieval-grounded — stick to rehearsed CD-X1 phrasings; re-ask with the lesson's terminology |
| Login fails | Use the backup admin account; if both fail, reseed QA accounts (see §7) |
| Course won't start | Reload `/corporate`, relaunch from a different course card (all 11 are equivalent demos) |
| Total stack failure | Fall back to the recorded video `careers_demo.mp4` (verify freshness beforehand; regenerate via `scripts/generate_pitch_video.py`) |

## 9. Maintenance

- The corporate lesson set is **pinned** in CD-B6 and CD-E1: adding/removing a corporate course intentionally means updating `test_corporate_lessons.py`, `corporate_programs.py`, and `catalog.spec.ts` together.
- Re-run `make demo-check` after any change touching `apps/web/app/corporate/`, `apps/web/app/jobs/`, `services/curriculum/`, or `services/orchestrator/curriculum.py`.
- Post-demo follow-ups: Maestro for mobile Careers; promote demo-check to nightly CI; the broader platform gaps live in the [master V&V plan](vv-master-plan.md).
