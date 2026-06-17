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

The current build runs the **Phase&nbsp;1 teaching loop end to end** in the web app:
start a class, the Teaching Director presents slides with narration, and you can
ask the AI tutor questions that are answered with RAG over the lesson material.

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

| Phase | Scope | Status |
| --- | --- | --- |
| **phase0** | Foundations: monorepo, provider abstraction (local+cloud + factory), config contracts, db migrations, sample-curriculum RAG skeleton, vLLM serving config, local docker compose, per-service Dockerfiles, Makefile, CI | ✅ Implemented |
| **phase1** | Live AI teacher in the web app: Director + Lesson Delivery + Tutor; slide presentation + (text) narration; text-chat Q&amp;A via RAG | ◑ Core loop working (text); real-time LiveKit audio/agent-runtime room wiring is stubbed |
| **phase2** | Multilingual + voice: streaming ASR, language ID, NLLB translation, multilingual TTS | ⬜ Planned (interfaces stubbed) |
| **phase3** | Perception (consent-gated): face recognition + attention/gaze | ⬜ Planned (interfaces + consent gate stubbed) |
| **phase4** | Memory &amp; adaptive learning: profiles, mastery graph, cross-class context | ⬜ Planned (service skeleton + schema) |
| **phase5** | Assessment: quizzes, definition checks, polls, mastery loop | ⬜ Planned |
| **phase6** | Curriculum suite / CMS + teacher dashboard | ⬜ Planned (service skeleton) |
| **phase6b** | Monetization &amp; billing: entitlements API, Stripe (cloud) / sandbox (local) | ⬜ Planned (service skeleton + schema + provider) |
| **phase7** | Zoom bridge &rarr; LiveKit | ⬜ Planned |
| **phase8** | Teams bridge (.NET Graph Communications) | ⬜ Planned |
| **phase9** | Google Meet / Chat bridge | ⬜ Planned |
| **phase10** | Hardening &amp; scale: latency, GPU batching/pooling, observability, fine-tuning | ⬜ Planned |

> **In short:** phase0 foundations are in place and a working phase1 slice runs
> end to end. Phases 2&ndash;10 are not built yet &mdash; their interfaces, service
> skeletons, schemas, and config are scaffolded so they can be filled in without
> reworking the architecture. (Cloud k8s manifests under `infra/k8s` are also not
> created yet.)

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
- **Speech / Vision (planned):** Whisper large-v3, NLLB-200, XTTS-v2;
  InsightFace/ArcFace + MediaPipe, self-hosted.
- **Data:** Postgres (+pgvector), Redis, S3-compatible object storage (MinIO local).
- **Infra:** docker compose (local) / Kubernetes + GPU pool (cloud); GitHub Actions CI.

## Repository layout

```
apps/web                 Next.js app (live class, dashboards, consent)
apps/agent-runtime       Python LiveKit Agents worker (teaching brain)
services/orchestrator    Director + lesson/slide/RAG Q&A API (FastAPI)
services/memory          profiles, mastery graph (skeleton)
services/speech          ASR/MT/TTS gateway (skeleton)
services/perception      vision: face + attention, consent-gated (skeleton)
services/curriculum      content/CMS API (skeleton)
services/billing         plans, entitlements API (skeleton)
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

The shared factory test proves local-vs-cloud provider selection by env; the
orchestrator tests exercise the full start &rarr; advance &rarr; ask teaching flow; each
service skeleton verifies `/health` plus its domain stub.

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
