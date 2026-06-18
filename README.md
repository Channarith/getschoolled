<p align="center">
  <img src="docs/images/hero.png" alt="AI Classroom - Agentic Online Education Platform" width="100%" />
</p>

<h1 align="center">AI Classroom &middot; Agentic Online Education Platform</h1>

<p align="center">
  A multi-agent AI instructor that teaches live online classes (group and 1:1),
  perceives the room over webcam, remembers every student across sessions, and
  adapts pedagogy in real time &mdash; built own-platform first, then bridged into
  Zoom / Teams / Meet.
</p>

<p align="center">
  <img src="docs/images/logo.png" alt="AI Classroom logo" width="120" />
</p>

---

> **Project conventions:** plain-text/code only (no markdown beyond this README and
> `AGENTS.md`), always `python3`, dual-mode via env (no code forks), pinned
> dependency versions, and `CHANGELOG.txt` updated on every meaningful change.
> See `docs/plan.txt` and `docs/cloud-agent-task.txt` for the full spec.

## Table of contents

- [What is this?](#what-is-this)
- [Screenshots](#screenshots)
- [Build status by phase](#build-status-by-phase)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Running the app](#running-the-app)
- [Testing &amp; linting](#testing--linting)
- [Configuration &amp; dual-mode](#configuration--dual-mode)
- [Full stack with Docker Compose](#full-stack-with-docker-compose)
- [The agents](#the-agents)
- [Compliance](#compliance)
- [Contributing](#contributing)

## What is this?

The platform pairs an **own agentic orchestration layer** with a base education
LLM (open-weight, RAG now, fine-tune later) on top of **LiveKit** (WebRTC) as the
real-time media backbone. The same codebase runs **fully local** (single
machine / docker compose) or **against a cloud backend**, switched purely by
configuration &mdash; there are no code forks. Every heavy capability (LLM, speech,
vision, media, object store, payments) sits behind a narrow interface with a
local and a cloud implementation, chosen at startup by a config-driven factory.

The current build runs the **live teaching loop end to end** in the web app
(start a class, the Teaching Director presents slides, ask the AI tutor questions
answered with RAG), plus working **face recognition**, **adaptive
pacing/difficulty**, **assessment** (quizzes/polls), a **curriculum CMS**,
**entitlements + multiple payment methods**, and **multilingual delivery
routing** &mdash; all testable offline. Real-time voice/video, GPU model serving,
and the external platform bridges (Zoom/Teams/Meet) are wired behind config and
need infra/credentials to run. See the status table below.

## Screenshots

| Live class &mdash; slide delivery | Live class &mdash; ask the AI teacher (RAG + citations) |
| --- | --- |
| <img src="docs/images/live_class_slide.webp" alt="Live class slide" /> | <img src="docs/images/live_class_ask.webp" alt="Ask the AI teacher" /> |

| Home | Teacher dashboard (agent roster) | Biometric consent |
| --- | --- | --- |
| <img src="docs/images/home.webp" alt="Home page" /> | <img src="docs/images/dashboard.webp" alt="Teacher dashboard" /> | <img src="docs/images/consent.webp" alt="Consent page" /> |

## Build status by phase

The roadmap (`docs/plan.txt`) spans phase0 &rarr; phase10. This is the honest
current state of the repository:

Legend: ✅ implemented &amp; tested · ◑ partial (offline logic done; needs GPU/media/external infra) · ⬜ scaffolded behind interfaces/config.

| Phase | Scope | Status |
| --- | --- | --- |
| **phase0** | Foundations: monorepo, provider abstraction (local+cloud + factory), config contracts, db migrations, sample-curriculum RAG skeleton, vLLM serving config, local docker compose, per-service Dockerfiles, Makefile, CI | ✅ Implemented |
| **phase1** | Live AI teacher in the web app: Director + Lesson Delivery + Tutor; slide presentation + (text) narration; text-chat Q&amp;A via RAG | ◑ Text teaching loop works end to end; real-time LiveKit audio / agent-runtime room wiring still needs media infra |
| **phase2** | Multilingual + voice: language coverage (26 langs), per-student delivery routing (translate? pair supported? native XTTS vs cloud-TTS fallback) | ◑ Routing/coverage logic implemented &amp; tested; real streaming ASR / NLLB / XTTS need GPU model serving |
| **phase3** | Perception (consent-gated): face recognition + attention | ✅ Real self-hosted face recognition (OpenCV YuNet + SFace), consent-gated, enroll/identify, extensively tested |
| **phase4** | Memory &amp; adaptive learning: profiles, mastery, learning-behavior signals, pacing/difficulty policy (solo vs group) | ✅ Implemented &amp; tested (adaptive policy + behavior tracking) |
| **phase5** | Assessment: quizzes, definition checks, polls, mastery feedback loop | ✅ Implemented &amp; tested (MCQ generation, grading, polls) |
| **phase6** | Curriculum suite / CMS: author/import/manage decks | ✅ Implemented &amp; tested (deck CRUD + text import + presentation view) |
| **phase6b** | Monetization &amp; billing: entitlements API + payment methods (card, Apple/Google Pay, Cash App, PayPal, Venmo, Zelle); Stripe (cloud) / sandbox (local) | ✅ Implemented &amp; tested (sandbox simulates all methods offline) |
| **phase7** | Zoom bridge &rarr; LiveKit | ⬜ Scaffolded: `MediaBridge` interface + capability registry + credential checks; needs Zoom SDK + creds |
| **phase8** | Teams bridge (.NET Graph Communications) | ⬜ Scaffolded; needs Azure/Graph creds + a .NET media bot |
| **phase9** | Google Meet / Chat bridge | ⬜ Scaffolded; needs Google Workspace creds |
| **phase10** | Hardening &amp; scale: latency, GPU batching/pooling, observability, fine-tuning | ◑ Latency budget + recorder implemented &amp; tested; GPU/autoscale/observability stack needs infra |

> **In short:** phases 0, 3, 4, 5, 6, and 6b are implemented and tested; phases 1,
> 2, and 10 have their offline logic done but need GPU/media infra for the
> remaining pieces; phases 7&ndash;9 (platform bridges) are scaffolded behind a
> stable interface and need external SDKs/credentials to run. The whole backend
> suite is green (120+ tests). Cloud k8s manifests under `infra/k8s` ship from the
> phase0 foundations; real model serving and platform bots require credentials/GPU.

## Platform extensions (in progress)

Backend capabilities being added phase-by-phase (each its own version release):

- Course validation - pluggable, key-gated `SearchProvider` (Bing/Google CSE/Brave/Kagi/Baidu + offline mock) to corroborate course content against the web. `factory.search_engines()` returns whichever engines have API keys configured. Endpoints: `POST /validate/claim` and `POST /decks/{id}/validate` (per-claim supported/unverified/contradicted + confidence + citations).

## Architecture

```
                 Browser (apps/web, Next.js)
                          |
                          v
        Orchestrator API (services/orchestrator, FastAPI)
        Teaching Director: lessons, sessions, slides, RAG Q&A
                          |
              packages/shared  ProviderFactory
        (selects local vs cloud per capability, by env)
   ┌──────────┬──────────┬──────────┬──────────┬──────────┐
  LLM       Speech     Vision      Media   ObjectStore  Payment
 (vLLM/    (Whisper/  (InsightFace (LiveKit) (MinIO/S3) (Stripe/
  Ollama)   XTTS)      /MediaPipe)                        sandbox)

  Supporting services (FastAPI): memory · speech · perception ·
  curriculum · billing        Worker: apps/agent-runtime (LiveKit Agents)
  Data: Postgres + pgvector · Redis · object store
```

**Dual-mode** is the core idea: `DEPLOY_MODE=local|cloud` sets the default
implementation family, and each capability can be overridden independently (for
example, keep biometrics local even in cloud for compliance) without forking code.

## Tech stack

- **Frontend:** Next.js 14 + React 18 + TypeScript (LiveKit JS SDK to come).
- **Backend / agents:** Python, FastAPI, LiveKit Agents, LangGraph (Director).
- **LLM serving:** open-weight base model via vLLM; RAG now, fine-tune later.
- **Vision (implemented):** self-hosted OpenCV YuNet + SFace face recognition (CPU).
- **Speech (provider-wired):** Whisper large-v3 (ASR), NLLB-200 (translation),
  XTTS-v2 (TTS) behind the SpeechProvider; need GPU model serving to run.
- **Data:** Postgres (+pgvector), Redis, S3-compatible object storage (MinIO local).
- **Infra:** docker compose (local) / Kubernetes + GPU pool (cloud); GitHub Actions CI.

## Repository layout

```
apps/web                 Next.js app (live class, dashboards, consent)
apps/agent-runtime       Python LiveKit Agents worker (teaching brain)
services/orchestrator    Director + lesson/slide/RAG Q&A API (FastAPI)
services/memory          profiles, mastery, learning-behavior signals
services/speech          language coverage + delivery routing (ASR/MT/TTS behind provider)
services/perception      vision: face recognition + attention, consent-gated
services/curriculum      content/CMS API: deck authoring/import + RAG search
services/billing         plans, entitlements + payment methods (Stripe/sandbox)
packages/shared          provider interfaces + local/cloud impls + factory + schemas
config/                  per-mode env contracts (local.env, cloud.env)
db/migrations            SQL schema (consent/compliance + billing/entitlements)
models/serving           vLLM serving config (weights downloaded at runtime)
sample-curriculum/       sample lessons for the RAG skeleton
infra/compose            local docker compose (full stack)
docs/                    plan.txt, cloud-agent-task.txt, images
```

## Prerequisites

- **Python 3.11+** (the dev environment uses system Python 3.12; `.python-version`
  requests 3.11 &mdash; both work).
- **Node.js 20+** and **pnpm 10+** for the web app.
- **Docker** (optional) only for the full containerized stack.

## Quickstart

```bash
# 1. Backend: create the virtualenv and install dev deps (editable shared package)
make setup            # == python3 -m venv .venv && pip install -r requirements-dev.txt

# 2. Web: install dependencies
make setup-web        # == cd apps/web && pnpm install

# 3. Run the tests
make test             # all Python tests (shared + services + agent-runtime)
make test-web         # web typecheck + lint
```

> On a fresh Debian/Ubuntu machine you may first need the venv package:
> `sudo apt-get install -y python3.12-venv`.

## Running the app

Run the two dev processes in separate terminals (start the orchestrator first):

```bash
# Terminal 1 - Orchestrator API (http://localhost:8000)
. .venv/bin/activate
export DEPLOY_MODE=local CURRICULUM_DIR="$PWD/sample-curriculum"
cd services/orchestrator && uvicorn app.main:app --reload --port 8000
#   or: make dev-orchestrator

# Terminal 2 - Web app (http://localhost:3000)
make dev-web          # == cd apps/web && pnpm run dev
```

Then open **http://localhost:3000/class**, start the "Intro to Photosynthesis"
lesson, advance slides, and ask the AI teacher a question. The web app reads the
backend URL from `NEXT_PUBLIC_ORCHESTRATOR_URL` (default `http://localhost:8000`).

Quick API check:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/lessons
```

## Testing &amp; linting

| Target | Command |
| --- | --- |
| All Python tests | `make test` |
| Single package/service | `cd <path> && python -m pytest -q` |
| Web typecheck + lint | `make test-web` |
| Web production build | `make build-web` |
| Validate compose | `make compose-config` (requires Docker) |

The full backend suite (120+ tests) is green: provider local-vs-cloud selection,
the orchestrator teaching flow (start &rarr; advance &rarr; ask) plus adaptive/assessment
APIs, real face-recognition accuracy on a labeled dataset, CMS deck CRUD/import,
multilingual delivery routing, payment methods, and bridge/latency scaffolds.

## Configuration &amp; dual-mode

Configuration lives in `config/local.env` and `config/cloud.env`:

- `DEPLOY_MODE=local|cloud` selects the default implementation family.
- Per-component overrides (`LLM_MODE`, `SPEECH_MODE`, `VISION_MODE`,
  `MEDIA_MODE`, `OBJECT_STORE_MODE`, `PAYMENT_MODE`) override a single capability;
  **blank means "inherit `DEPLOY_MODE`"**.
- Endpoints/connection strings (`LLM_BASE_URL`, `LIVEKIT_URL`, `DATABASE_URL`,
  `REDIS_URL`, `OBJECT_STORE_ENDPOINT`, ...) are read by the cloud impls.

In **local** mode the heavy providers are deterministic, dependency-free stubs so
the teaching loop runs offline (no GPU/keys). In **cloud** mode they target
managed/GPU backends and raise `CloudProviderUnavailable` until real endpoints
and credentials are wired.

## Full stack with Docker Compose

`infra/compose/docker-compose.yml` defines the full local stack: `web`,
`orchestrator`, the supporting services, `agent-runtime`, `livekit`,
`postgres` (pgvector), `redis`, and `minio`.

```bash
docker compose -f infra/compose/docker-compose.yml config   # validate
docker compose -f infra/compose/docker-compose.yml up --build
```

## The agents

| Agent | Responsibility |
| --- | --- |
| Teaching Director | Lesson state machine; balances teach vs answer vs quiz vs re-engage |
| Lesson Delivery | Walks the deck, narrates slides via TTS, plays videos |
| Q&amp;A / Tutor | Chat + voice questions, RAG over curriculum, answers in the asker's language |
| Assessment | Pop quizzes, definition/key-point checks, polls, mastery |
| Perception | Consent-gated face recognition + attention/gaze scoring |
| Speech | Streaming multilingual ASR, language ID, translation, TTS |
| Memory / Profile | Long-term per-student profile, mastery graph, cross-class history |
| Consent / Compliance | Gates biometric features; enforces retention/deletion (FERPA/GDPR/BIPA) |

## Compliance

Biometric features are **opt-in** and consent-gated, with a name-only fallback.
Face embeddings are stored encrypted, deletable on request, and never leave the
configured boundary. Recording and data-retention disclosures are surfaced in the
app (and, later, in bridged meetings).

## Contributing

- Do **not** add new markdown files (this `README.md` and `AGENTS.md` aside) &mdash;
  use code, comments, and plain-text `.txt`.
- Always use `python3` (never `python`).
- Keep the dual-mode contract: no code forks; switch behavior via env only.
- Pin dependency versions; keep large model weights out of the repo.
- Update `CHANGELOG.txt` with every meaningful change.
- See `AGENTS.md` for environment/run caveats for automated agents.
